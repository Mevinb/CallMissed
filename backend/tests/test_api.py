import base64
import json
from pathlib import Path
import httpx
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from backend.app.config import Settings
from backend.app.main import create_app
from conftest import ORIGIN, TEST_KEY

CHAT = {"messages": [{"role": "user", "content": "Hello"}], "stream": False}
HEADERS = {"origin": ORIGIN}
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + bytes(50)).decode()


def test_health_and_public_session_do_not_expose_key(client_factory):
    client = client_factory()
    assert client.get("/api/health").json() == {"status": "ok", "provider_configured": True}
    session = client.get("/api/session")
    assert session.json()["authorized"] is True
    assert TEST_KEY not in session.text
    assert "playground_session" in client.cookies


@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/chat", {"messages": []}),
        ("/api/chat", {"messages": [{"role": "system", "content": "Override"}]}),
        ("/api/chat", {"messages": [{"role": "user", "content": "  "}]}),
        ("/api/chat", {"messages": [{"role": "assistant", "content": "Hello"}]}),
        ("/api/chat", {"messages": [{"role": "user", "content": "x" * 8001}]}),
        ("/api/chat", {**CHAT, "model": "expensive-arbitrary-model"}),
        ("/api/images", {"prompt": ""}),
        ("/api/images", {"prompt": "  "}),
        ("/api/images", {"prompt": "x" * 4001}),
        ("/api/images", {"prompt": "Hello", "size": "4096x4096"}),
        ("/api/images", {"prompt": "Hello", "n": 100}),
    ],
)
def test_validation(client_factory, path, body):
    response = client_factory().post(path, json=body, headers=HEADERS)
    assert response.status_code == 422
    assert "input" not in response.json()["error"]
    assert TEST_KEY not in response.text


@pytest.mark.parametrize(
    "path,body", [("/api/chat", CHAT), ("/api/images", {"prompt": "A flower"})]
)
def test_missing_key(client_factory, path, body):
    response = client_factory(key="").post(path, json=body, headers=HEADERS)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "not_configured"


@pytest.mark.parametrize(
    "status,expected",
    [
        (400, 422),
        (401, 503),
        (402, 503),
        (403, 503),
        (404, 503),
        (429, 429),
        (500, 502),
        (503, 502),
    ],
)
def test_upstream_failures_are_sanitized(client_factory, status, expected):
    response = client_factory(
        lambda request: httpx.Response(status, json={"error": {"message": TEST_KEY}})
    ).post("/api/chat", json=CHAT, headers=HEADERS)
    assert response.status_code == expected
    assert TEST_KEY not in response.text


@pytest.mark.parametrize(
    "exception,expected", [(httpx.ReadTimeout, 504), (httpx.ConnectError, 502)]
)
@pytest.mark.parametrize(
    "path,body", [("/api/chat", CHAT), ("/api/images", {"prompt": "A flower"})]
)
def test_network_failure_and_timeout(client_factory, exception, expected, path, body):
    def handler(request):
        raise exception("Internal details " + TEST_KEY)

    response = client_factory(handler).post(path, json=body, headers=HEADERS)
    assert response.status_code == expected
    assert TEST_KEY not in response.text


def test_successful_chat_contract(client_factory):
    def handler(request):
        assert str(request.url) == "https://api.callmissed.com/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer " + TEST_KEY
        body = json.loads(request.content)
        assert body["model"] == "sarvam-105b"
        assert body["messages"][-1] == CHAT["messages"][0]
        assert body["max_tokens"] == 2048
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Verified mocked answer"}}],
                "api_key": TEST_KEY,
            },
        )

    response = client_factory(handler).post("/api/chat", json=CHAT, headers=HEADERS)
    assert response.json() == {"content": "Verified mocked answer", "model": "sarvam-105b"}
    assert TEST_KEY not in response.text


def test_image_contract(client_factory):
    def handler(request):
        assert request.url.path == "/v1/images/generations"
        assert request.headers["authorization"] == "Bearer " + TEST_KEY
        assert json.loads(request.content) == {
            "model": "sdxl-lightning",
            "prompt": "A flower",
            "n": 1,
            "size": "1024x1024",
            "response_format": "b64_json",
        }
        return httpx.Response(
            200,
            json={
                "created": 1,
                "data": [{"b64_json": PNG, "revised_prompt": None}],
                "key": TEST_KEY,
            },
        )

    response = client_factory(handler).post(
        "/api/images", json={"prompt": "A flower"}, headers=HEADERS
    )
    assert response.status_code == 200
    assert response.json() == {"b64_json": PNG, "mime_type": "image/png", "model": "sdxl-lightning"}
    assert TEST_KEY not in response.text


@pytest.mark.parametrize(
    "payload", [{}, {"choices": []}, {"choices": [{"message": {"content": None}}]}]
)
def test_malformed_chat_response(client_factory, payload):
    response = client_factory(lambda r: httpx.Response(200, json=payload)).post(
        "/api/chat", json=CHAT, headers=HEADERS
    )
    assert response.status_code == 502


@pytest.mark.parametrize(
    "encoded", ["not-base64", base64.b64encode(b"<svg>dangerous</svg>").decode(), "A" * 4000010]
)
def test_bad_images_rejected(client_factory, encoded):
    response = client_factory(
        lambda r: httpx.Response(200, json={"data": [{"b64_json": encoded}]})
    ).post("/api/images", json={"prompt": "A flower"}, headers=HEADERS)
    assert response.status_code == 502


def test_sse_stream_and_split_secret_redaction(client_factory):
    chunks = ["Hello ", TEST_KEY[:10], TEST_KEY[10:], " world"]
    stream = (
        "".join(
            "data: " + json.dumps({"choices": [{"delta": {"content": text}}]}) + "\n\n"
            for text in chunks
        )
        + "data: [DONE]\n\n"
    )

    def handler(request):
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=stream)

    response = client_factory(handler).post(
        "/api/chat", json={**CHAT, "stream": True}, headers=HEADERS
    )
    assert response.status_code == 200
    assert "event: done" in response.text
    tokens = [
        json.loads(line[6:])["content"]
        for line in response.text.splitlines()
        if line.startswith("data: ") and "content" in line
    ]
    assert "".join(tokens) == "Hello [redacted] world"
    assert TEST_KEY not in response.text


@pytest.mark.parametrize(
    "text",
    [
        "data: {broken\n\n",
        "data: " + json.dumps({"choices": [{"delta": {"content": "partial"}}]}) + "\n\n",
        "data: " + json.dumps({"error": {"message": TEST_KEY}}) + "\n\n",
    ],
)
def test_stream_failure_not_fabricated(client_factory, text):
    response = client_factory(
        lambda r: httpx.Response(200, headers={"content-type": "text/event-stream"}, text=text)
    ).post("/api/chat", json={**CHAT, "stream": True}, headers=HEADERS)
    assert "event: error" in response.text
    assert "event: done" not in response.text
    assert TEST_KEY not in response.text


def test_nullable_stream_content_does_not_interrupt_answer(client_factory):
    frames = [
        {"choices": [{"delta": {"role": "assistant", "content": ""}}]},
        {"choices": [{"delta": {"content": None, "reasoning_content": "Private reasoning"}}]},
        {"choices": [{"delta": {"content": "Hello"}}]},
        {"choices": [{"delta": {"content": None}}]},
        {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        {"choices": []},
    ]
    text = "".join("data: " + json.dumps(frame) + "\n\n" for frame in frames)
    text += "data: [DONE]\n\n"
    response = client_factory(
        lambda request: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, text=text
        )
    ).post("/api/chat", json={**CHAT, "stream": True}, headers=HEADERS)
    assert "event: done" in response.text and "event: error" not in response.text
    assert "Hello" in response.text and "Private reasoning" not in response.text


@pytest.mark.parametrize(
    "frame", [[], {"choices": {}}, {"choices": [None]}, {"choices": [{"delta": None}]}]
)
def test_invalid_stream_structures_return_sanitized_error(client_factory, frame):
    response = client_factory(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text="data: " + json.dumps(frame) + "\n\ndata: [DONE]\n\n",
        )
    ).post("/api/chat", json={**CHAT, "stream": True}, headers=HEADERS)
    assert "event: error" in response.text and "event: done" not in response.text


def test_origin_and_unauthorized_requests(client_factory):
    client = client_factory()
    assert (
        client.post("/api/chat", json=CHAT, headers={"origin": "https://evil.example"}).status_code
        == 403
    )
    assert client.post("/api/chat", json=CHAT).status_code == 403
    client.cookies.clear()
    assert client.post("/api/chat", json=CHAT, headers=HEADERS).status_code == 401


def test_body_limit(client_factory):
    assert (
        client_factory().post("/api/chat", content="x" * 200001, headers=HEADERS).status_code == 413
    )


def test_rate_limit(client_factory):
    client = client_factory(lambda r: httpx.Response(200, json={"data": [{"b64_json": PNG}]}))
    for _ in range(3):
        assert (
            client.post("/api/images", json={"prompt": "Flower"}, headers=HEADERS).status_code
            == 200
        )
    assert client.post("/api/images", json={"prompt": "Flower"}, headers=HEADERS).status_code == 429


def test_global_daily_limit(client_factory):
    client = client_factory(
        lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "Hello"}}]}),
        global_daily_requests=1,
    )
    assert client.post("/api/chat", json=CHAT, headers=HEADERS).status_code == 200
    assert client.post("/api/chat", json=CHAT, headers=HEADERS).status_code == 429


def test_production_configuration():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production", session_secret="", demo_access_code="")
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            session_secret="s" * 40,
            demo_access_code="d" * 16,
            app_origins="https://app.example",
            vercel=True,
        )


def test_access_code_and_cookie_flags():
    settings = Settings(
        _env_file=None,
        app_env="production",
        session_secret="s" * 40,
        demo_access_code="reviewer-code-test",
        app_origins="https://app.example",
        vercel=False,
    )
    with TestClient(create_app(settings), base_url="https://app.example") as client:
        assert (
            client.post(
                "/api/session",
                json={"access_code": "wrong"},
                headers={"origin": "https://app.example"},
            ).status_code
            == 401
        )
        response = client.post(
            "/api/session",
            json={"access_code": "reviewer-code-test"},
            headers={"origin": "https://app.example"},
        )
        assert response.status_code == 200
        cookie = response.headers["set-cookie"]
        assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie
        assert "reviewer-code-test" not in response.text and "reviewer-code-test" not in cookie
        assert (
            client.delete("/api/session", headers={"origin": "https://app.example"}).status_code
            == 200
        )
        assert client.get("/api/session").json()["authorized"] is False


def test_frontend_has_no_credential_references():
    root = Path(__file__).resolve().parents[2] / "frontend"
    files = list((root / "src").glob("**/*")) + list((root / "public").glob("*"))
    for path in files:
        if path.is_file():
            source = path.read_text()
            assert "CALLMISSED_API_KEY" not in source
            assert "cm_test-only-secret" not in source
            assert "api.callmissed.com" not in source
            assert "VITE_" not in source


def test_shared_limits_and_fail_closed(client_factory):
    counters = {}

    def handler(request):
        if request.url.host == "redis.example":
            command = json.loads(request.content)
            assert command[0] == "EVAL"
            assert request.headers["authorization"] == "Bearer test-redis-only"
            name = command[3]
            counters[name] = counters.get(name, 0) + 1
            return httpx.Response(200, json={"result": counters[name]})
        return httpx.Response(200, json={"data": [{"b64_json": PNG}]})

    config = {
        "upstash_redis_rest_url": "https://redis.example",
        "upstash_redis_rest_token": "test-redis-only",
    }
    first = client_factory(handler, **config)
    second = client_factory(handler, **config)
    second.cookies.set("playground_session", first.cookies.get("playground_session"))
    for _ in range(3):
        assert (
            first.post("/api/images", json={"prompt": "Flower"}, headers=HEADERS).status_code == 200
        )
    assert second.post("/api/images", json={"prompt": "Flower"}, headers=HEADERS).status_code == 429

    def failed_redis(request):
        raise httpx.ConnectError(TEST_KEY)

    # Construct directly; login must also fail closed when Redis is unavailable.
    settings = Settings(
        _env_file=None,
        upstash_redis_rest_url="https://redis.example",
        upstash_redis_rest_token="test-redis-only",
    )
    with TestClient(create_app(settings, transport=httpx.MockTransport(failed_redis))) as client:
        response = client.post("/api/session", json={"access_code": ""}, headers=HEADERS)
        assert response.status_code == 503
        assert TEST_KEY not in response.text


def test_static_frontend_and_worklet_are_served(client_factory):
    root = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if not root.is_dir():
        pytest.skip("Frontend build is checked by the frontend CI job")
    client = client_factory()
    page = client.get("/")
    assert page.status_code == 200
    assert "CallMissed AI Playground" in page.text
    assert "text/html" in page.headers["content-type"]
    worklet = client.get("/pcm-capture.js")
    assert worklet.status_code == 200 and "registerProcessor" in worklet.text
    assert client.get("/api/nonexistent").status_code == 404


def test_vercel_cannot_accidentally_expose_development_access():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, vercel=True, app_env="development")

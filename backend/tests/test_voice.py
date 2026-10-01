import asyncio
import json
from contextlib import asynccontextmanager
import pytest
from fastapi import WebSocketDisconnect
from backend.app.services.voice import VOICE_URL
from conftest import ORIGIN, TEST_KEY


class FakeUpstream:
    def __init__(self):
        self.events = asyncio.Queue()
        self.events.put_nowait(json.dumps({"type": "Welcome", "request_id": "test"}))
        self.sent = []
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.events.get()

    async def send(self, frame):
        self.sent.append(frame)
        if isinstance(frame, str) and json.loads(frame).get("type") == "Settings":
            self.events.put_nowait(json.dumps({"type": "SettingsApplied"}))
            self.events.put_nowait(
                json.dumps(
                    {"type": "ConversationText", "role": "assistant", "content": "Mocked greeting"}
                )
            )
            self.events.put_nowait(bytes([0, 0]) * 480)
        elif isinstance(frame, bytes):
            self.events.put_nowait(json.dumps({"type": "UserStartedSpeaking"}))


@pytest.fixture
def voice_provider():
    upstream = FakeUpstream()
    received = {}

    @asynccontextmanager
    async def connector(url, **kwargs):
        received.update(url=url, **kwargs)
        try:
            yield upstream
        finally:
            upstream.closed = True

    return connector, upstream, received


def test_voice_handshake_audio_and_cleanup(client_factory, voice_provider):
    connector, upstream, received = voice_provider
    client = client_factory(voice_connector=connector)
    with client.websocket_connect("/api/voice", headers={"origin": ORIGIN}) as socket:
        ready = socket.receive_json()
        assert ready["type"] == "SettingsApplied" and ready["sample_rate"] == 24000
        assert socket.receive_json() == {
            "type": "ConversationText",
            "role": "assistant",
            "content": "Mocked greeting",
        }
        assert len(socket.receive_bytes()) == 960
        socket.send_bytes(bytes([0, 0]) * 480)
        assert socket.receive_json() == {"type": "UserStartedSpeaking"}
        socket.send_json({"type": "Stop"})
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()
    assert received["url"] == VOICE_URL
    assert received["additional_headers"] == {"Authorization": "Token " + TEST_KEY}
    settings = json.loads(upstream.sent[0])
    assert settings["type"] == "Settings"
    assert settings["audio"]["input"] == {"encoding": "linear16", "sample_rate": 24000}
    assert settings["agent"]["stt"]["model"] == "saaras:v3"
    assert upstream.closed
    assert not client.app.state.voice_sessions


@pytest.mark.parametrize(
    "origin,key,clear_cookie",
    [("https://evil.example", TEST_KEY, False), (ORIGIN, "", False), (ORIGIN, TEST_KEY, True)],
)
def test_voice_rejects_unauthorized_or_unconfigured(client_factory, origin, key, clear_cookie):
    client = client_factory(key=key)
    if clear_cookie:
        client.cookies.clear()
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/voice", headers={"origin": origin}):
            pass


def test_invalid_audio_and_unsafe_controls(client_factory, voice_provider):
    connector, upstream, _ = voice_provider
    client = client_factory(voice_connector=connector)
    with client.websocket_connect("/api/voice", headers={"origin": ORIGIN}) as socket:
        socket.receive_json()
        socket.receive_json()
        socket.receive_bytes()
        socket.send_json({"type": "Settings", "api_key": TEST_KEY})
        event = socket.receive_json()
        assert event["type"] == "Error"
        assert TEST_KEY not in json.dumps(event)
    assert upstream.closed


def test_voice_provider_timeout(client_factory):
    @asynccontextmanager
    async def connector(*args, **kwargs):
        raise TimeoutError(TEST_KEY)
        yield

    client = client_factory(voice_connector=connector)
    with client.websocket_connect("/api/voice", headers={"origin": ORIGIN}) as socket:
        event = socket.receive_json()
        assert event["code"] == "voice_timeout"
        assert TEST_KEY not in json.dumps(event)
    assert not client.app.state.voice_sessions

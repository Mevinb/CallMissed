import httpx
import pytest
from fastapi.testclient import TestClient
from backend.app.config import Settings
from backend.app.main import create_app

ORIGIN = "http://localhost:5173"
TEST_KEY = "cm_test-only-secret-not-a-real-key"


@pytest.fixture
def client_factory():
    clients = []

    def factory(handler=None, key=TEST_KEY, voice_connector=None, **settings):
        config = Settings(
            _env_file=None,
            callmissed_api_key=key,
            session_secret="test-session-secret-with-at-least-32-chars",
            demo_access_code="",
            app_env="development",
            app_origins=ORIGIN,
            vercel=False,
            **settings,
        )

        def no_network(request):
            raise AssertionError("Unexpected external request in automated tests")

        app = create_app(config, httpx.MockTransport(handler or no_network), voice_connector)
        client = TestClient(app, raise_server_exceptions=False)
        client.__enter__()
        assert (
            client.post(
                "/api/session", json={"access_code": ""}, headers={"origin": ORIGIN}
            ).status_code
            == 200
        )
        clients.append(client)
        return client

    yield factory
    for client in reversed(clients):
        client.__exit__(None, None, None)

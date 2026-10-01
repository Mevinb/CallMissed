import asyncio
import json
import os
import subprocess
from types import SimpleNamespace

import httpx
import pytest

from backend.app.config import Settings
from backend.app.errors import AppError
from backend.app.security import RateLimiter
from backend.app.voice_slots import ACQUIRE, RELEASE, VoiceSlots


@pytest.fixture
async def slots_factory():
    """Mock Upstash transport; optionally evaluate Lua in an isolated local Redis."""
    leases, active = {}, set()
    clients = []
    command_log = []
    redis_socket = os.environ.get("CALLMISSED_TEST_REDIS_SOCKET")
    redis_cli = os.environ.get("CALLMISSED_TEST_REDIS_CLI")

    def handler(request):
        command = json.loads(request.content)
        command_log.append(command)
        assert request.headers["authorization"] == "Bearer test-redis-only"
        if redis_socket and redis_cli:
            process = subprocess.run(
                [redis_cli, "--json", "-s", redis_socket, *command],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            result = json.loads(process.stdout)
        else:
            _, script, key_count, session, global_key, token, *args = command
            assert key_count == "2" and global_key.endswith(":active")
            if script == ACQUIRE:
                assert args == ["300", "4"]
                result = int(session not in leases and len(active) < 4)
                if result:
                    leases[session] = token
                    active.add(token)
            else:
                assert script == RELEASE
                if leases.get(session) == token:
                    del leases[session]
                result = int(token in active)
                active.discard(token)
        return httpx.Response(200, json={"result": result})

    def factory():
        settings = Settings(
            _env_file=None,
            vercel=False,
            upstash_redis_rest_url="https://redis.example",
            upstash_redis_rest_token="test-redis-only",
        )
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        clients.append(client)
        limiter = RateLimiter(settings, client)
        # Unique namespaces keep real local Redis checks independent too.
        return VoiceSlots(settings, limiter, f"callmissed:{{test-{id(command_log)}}}")

    yield factory, command_log
    for client in clients:
        await client.aclose()


@pytest.mark.asyncio
async def test_one_session_across_workers_and_owned_release(slots_factory):
    factory, commands = slots_factory
    first, second = factory(), factory()
    token = await first.acquire("same-browser")
    assert "same-browser" not in json.dumps(commands)
    with pytest.raises(AppError, match="already active") as caught:
        await second.acquire("same-browser")
    assert caught.value.code == "voice_busy"
    await second.release("same-browser", "incorrect-token")
    with pytest.raises(AppError):
        await second.acquire("same-browser")
    await first.release("same-browser", token)
    new_token = await second.acquire("same-browser")
    assert new_token != token
    # A late release from an old connection cannot delete the newer lease.
    await first.release("same-browser", token)
    with pytest.raises(AppError):
        await first.acquire("same-browser")
    await second.release("same-browser", new_token)


@pytest.mark.asyncio
async def test_global_cap_across_workers_and_cleanup(slots_factory):
    factory, _ = slots_factory
    workers = [factory() for _ in range(8)]
    results = await asyncio.gather(
        *(worker.acquire(str(i)) for i, worker in enumerate(workers)), return_exceptions=True
    )
    assert sum(isinstance(x, str) for x in results) == 4
    failures = [x for x in results if isinstance(x, AppError)]
    assert len(failures) == 4 and all(x.status == 429 for x in failures)
    for i, token in enumerate(results):
        if isinstance(token, str):
            await workers[i].release(str(i), token)
    token = await workers[-1].acquire("new-call")
    await workers[-1].release("new-call", token)


@pytest.mark.asyncio
async def test_local_slots_duplicate_cap_and_release():
    settings = Settings(_env_file=None, vercel=False, upstash_redis_rest_url="")
    slots = VoiceSlots(settings, None)
    tokens = [await slots.acquire(str(i)) for i in range(4)]
    with pytest.raises(AppError):
        await slots.acquire("0")
    with pytest.raises(AppError):
        await slots.acquire("new")
    await slots.release("0", "wrong-owner")
    assert len(slots.active) == 4
    await slots.release("0", tokens[0])
    token = await slots.acquire("new")
    await slots.release("new", token)
    for i in range(1, 4):
        await slots.release(str(i), tokens[i])
    assert not slots.active


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [True, -1, 2, "1", None])
async def test_redis_invalid_admission_fails_closed(result):
    settings = Settings(
        _env_file=None, vercel=False, upstash_redis_rest_url="https://redis.example"
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"result": result}))
    ) as client:
        slots = VoiceSlots(settings, RateLimiter(settings, client))
        with pytest.raises(AppError) as caught:
            await slots.acquire("browser")
        assert caught.value.status == 503 and not slots.active


@pytest.mark.asyncio
async def test_redis_outage_fails_closed():
    def offline(request):
        raise httpx.ConnectError("private transport details")

    settings = Settings(
        _env_file=None, vercel=False, upstash_redis_rest_url="https://redis.example"
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(offline)) as client:
        slots = VoiceSlots(settings, RateLimiter(settings, client))
        with pytest.raises(AppError) as caught:
            await slots.acquire("browser")
        assert caught.value.code == "limits_unavailable"
        assert "private" not in caught.value.message


@pytest.mark.asyncio
async def test_lease_released_when_accept_fails(client_factory):
    from backend.app.routes.voice import voice

    client = client_factory()
    browser = SimpleNamespace(
        app=client.app,
        headers={"origin": "http://localhost:5173"},
        cookies={"playground_session": client.cookies.get("playground_session")},
    )

    async def broken_accept():
        raise RuntimeError("Browser disconnected before acceptance")

    browser.accept = broken_accept
    await voice(browser)
    assert not client.app.state.voice_slots.active

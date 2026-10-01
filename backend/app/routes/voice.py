from contextlib import suppress
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..errors import AppError
from ..services.voice import relay_voice

router = APIRouter()


@router.websocket("/voice")
async def voice(browser: WebSocket):
    state = browser.app.state
    accepted = False
    identity = None
    lease = None
    try:
        state.sessions.check_origin(browser.headers.get("origin"))
        identity = state.sessions.verify(browser.cookies.get("playground_session"))
        await state.limiter.hit(identity, "voice", 3, 3600)
        await state.limiter.hit("all", "daily", state.settings.global_daily_requests, 86400)
        state.callmissed.headers()
        lease = await state.voice_slots.acquire(identity)
        await browser.accept()
        accepted = True
        await relay_voice(browser, state)
    except AppError as exc:
        if accepted:
            with suppress(RuntimeError, WebSocketDisconnect):
                await browser.send_json({"type": "Error", "code": exc.code, "message": exc.message})
        else:
            # Do not accept unauthorized/origin-denied connections just to send an error.
            with suppress(RuntimeError):
                await browser.close(code=1008)
    except WebSocketDisconnect:
        pass
    except Exception:
        if accepted:
            with suppress(RuntimeError, WebSocketDisconnect):
                await browser.send_json(
                    {
                        "type": "Error",
                        "message": "The voice session ended unexpectedly. Please reconnect.",
                    }
                )
    finally:
        if accepted:
            with suppress(RuntimeError, WebSocketDisconnect):
                await browser.close(code=1000)
        if lease:
            # A failed Redis release must not mask relay cleanup. Expiry also
            # reclaims the slot if a worker crashes or Redis is unavailable.
            with suppress(AppError):
                await state.voice_slots.release(identity, lease)

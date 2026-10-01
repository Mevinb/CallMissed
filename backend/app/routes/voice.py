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
    try:
        state.sessions.check_origin(browser.headers.get("origin"))
        identity = state.sessions.verify(browser.cookies.get("playground_session"))
        await state.limiter.hit(identity, "voice", 3, 3600)
        await state.limiter.hit("all", "daily", state.settings.global_daily_requests, 86400)
        if identity in state.voice_sessions or len(state.voice_sessions) >= 4:
            raise AppError(
                429,
                "voice_busy",
                "A voice conversation is already active or the demo is busy. Try again shortly.",
            )
        state.callmissed.headers()
        state.voice_sessions.add(identity)
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
            state.voice_sessions.discard(identity)
            with suppress(RuntimeError, WebSocketDisconnect):
                await browser.close(code=1000)

import asyncio
import json
import time
from fastapi import WebSocketDisconnect
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus
from ..errors import AppError, upstream_error

VOICE_URL = "wss://api.callmissed.com/v2/voice/agent"
SAMPLE_RATE = 24000


def voice_settings(settings):
    return {
        "type": "Settings",
        "audio": {
            "input": {"encoding": "linear16", "sample_rate": SAMPLE_RATE},
            "output": {"encoding": "linear16", "sample_rate": SAMPLE_RATE},
        },
        "agent": {
            "prompt": "You are a helpful voice assistant in CallMissed AI Playground. Give concise, conversational answers.",
            "greeting": "Hi! What would you like to talk about?",
            "language": settings.voice_language,
            "llm": {"model": settings.voice_llm_model, "temperature": 0.4},
            "stt": {"model": settings.voice_stt_model},
            "tts": {"model": settings.voice_tts_model, "voice": settings.voice_name},
        },
    }


async def relay_voice(browser, state):
    key = state.settings.callmissed_api_key.get_secret_value()
    if not key:
        raise AppError(
            503,
            "not_configured",
            "The app owner needs to configure the CallMissed API key on the server.",
        )
    ready = asyncio.Event()
    tasks = []
    try:
        async with state.voice_connector(
            VOICE_URL,
            additional_headers={"Authorization": "Token " + key},
            open_timeout=15,
            close_timeout=3,
            max_size=256000,
            ping_interval=20,
            max_queue=8,
        ) as upstream:

            async def from_provider():
                async for frame in upstream:
                    if isinstance(frame, bytes):
                        if not ready.is_set() or len(frame) % 2:
                            raise AppError(
                                502,
                                "voice_protocol",
                                "The voice service returned invalid audio.",
                            )
                        await browser.send_bytes(frame)
                        continue
                    event = json.loads(frame)
                    kind = event.get("type")
                    if kind == "Welcome":
                        await upstream.send(json.dumps(voice_settings(state.settings)))
                    elif kind == "SettingsApplied":
                        ready.set()
                        await browser.send_json(
                            {
                                "type": kind,
                                "sample_rate": SAMPLE_RATE,
                                "max_seconds": state.settings.voice_max_seconds,
                            }
                        )
                    elif kind == "ConversationText":
                        if event.get("role") in ("user", "assistant") and isinstance(
                            event.get("content"), str
                        ):
                            await browser.send_json(
                                {
                                    "type": kind,
                                    "role": event["role"],
                                    "content": state.callmissed.safe_text(event["content"][:8000]),
                                }
                            )
                    elif kind in (
                        "UserStartedSpeaking",
                        "AgentThinking",
                        "AgentStartedSpeaking",
                        "AgentAudioDone",
                    ):
                        await browser.send_json({"type": kind})
                    elif kind == "Warning":
                        await browser.send_json(
                            {
                                "type": "Warning",
                                "message": "The voice service reported a warning. The session is still connected.",
                            }
                        )
                    elif kind == "Error":
                        raise AppError(
                            502,
                            "voice_provider",
                            "The voice session failed. Check the API plan, credits and selected models, then reconnect.",
                        )
                raise AppError(
                    502,
                    "voice_disconnected",
                    "The voice service disconnected. Start a new conversation.",
                )

            async def from_browser():
                window, count = time.monotonic(), 0
                control_window, controls = time.monotonic(), 0
                while True:
                    packet = await browser.receive()
                    if packet["type"] == "websocket.disconnect":
                        return
                    audio = packet.get("bytes")
                    if audio is not None:
                        if not ready.is_set() or not audio or len(audio) > 8192 or len(audio) % 2:
                            raise AppError(400, "voice_audio", "Invalid microphone audio frame.")
                        now = time.monotonic()
                        if now - window >= 1:
                            window, count = now, 0
                        count += len(audio)
                        if count > 96000:
                            raise AppError(
                                429,
                                "voice_audio_limit",
                                "Microphone data exceeded the session limit.",
                            )
                        await upstream.send(audio)
                    else:
                        # No browser-selected settings, models, tools or arbitrary provider commands.
                        now = time.monotonic()
                        if now - control_window >= 1:
                            control_window, controls = now, 0
                        controls += 1
                        if controls > 5:
                            raise AppError(
                                429, "voice_control_limit", "Too many voice control messages."
                            )
                        text = packet.get("text", "")
                        if len(text) > 100:
                            raise AppError(400, "voice_control", "Invalid voice control message.")
                        command = json.loads(text)
                        if command == {"type": "Stop"}:
                            return
                        if command == {"type": "KeepAlive"}:
                            await upstream.send(text)
                        else:
                            raise AppError(
                                400,
                                "voice_control",
                                "Unsupported voice control message.",
                            )

            async def handshake_deadline():
                await asyncio.wait_for(ready.wait(), timeout=20)
                await asyncio.sleep(state.settings.voice_max_seconds)
                raise AppError(
                    408,
                    "voice_duration",
                    "The demo conversation reached its time limit. Start a new conversation.",
                )

            tasks = [
                asyncio.create_task(fn())
                for fn in (from_provider, from_browser, handshake_deadline)
            ]
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
    except InvalidStatus as exc:
        raise upstream_error(exc.response.status_code) from None
    except TimeoutError:
        raise AppError(
            504,
            "voice_timeout",
            "The voice service took too long to connect. Try again.",
        ) from None
    except (ConnectionClosed, OSError):
        raise AppError(
            502,
            "voice_network",
            "The voice connection was interrupted. Start a new conversation.",
        ) from None
    except (ValueError, TypeError, KeyError):
        raise AppError(
            502, "voice_protocol", "The voice service returned an unreadable event."
        ) from None
    except WebSocketDisconnect:
        pass
    finally:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


DEFAULT_CONNECTOR = connect

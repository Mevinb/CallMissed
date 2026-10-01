"""Real CallMissed checks. Prints status only; never credentials or raw upstream errors."""

import argparse
import asyncio
import json
from pathlib import Path

import httpx
from websockets.asyncio.client import connect
from backend.app.config import Settings
from backend.app.models import ChatRequest, ImageRequest
from backend.app.services.callmissed import CallMissed
from backend.app.services.voice import VOICE_URL, voice_settings
from backend.app.errors import AppError


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", action="store_true")
    parser.add_argument("--voice", action="store_true")
    options = parser.parse_args()
    config = Settings()
    async with httpx.AsyncClient() as client:
        service = CallMissed(config, client)
        service.headers()
        response = await service.chat(
            ChatRequest(
                messages=[{"role": "user", "content": "Reply with a short greeting."}], stream=False
            )
        )
        if not response["content"]:
            raise AppError(502, "empty", "The provider returned no text.")
        print("PASS: real CallMissed chat returned nonempty text.")
        if options.image:
            import base64

            image = await service.image(
                ImageRequest(
                    prompt="A blue ceramic mug on a plain wooden table, studio photography",
                    size="512x512",
                )
            )
            destination = Path(
                "/tmp/callmissed-live-image."
                + ("png" if image["mime_type"] == "image/png" else "jpg")
            )
            destination.write_bytes(base64.b64decode(image["b64_json"]))
            print(
                "PASS: real CallMissed returned validated image bytes; saved to " + str(destination)
            )
        if options.voice:
            key = config.callmissed_api_key.get_secret_value()
            async with connect(
                VOICE_URL,
                additional_headers={"Authorization": "Token " + key},
                open_timeout=15,
                close_timeout=3,
            ) as socket:
                applied = False
                async with asyncio.timeout(45):
                    async for message in socket:
                        if isinstance(message, bytes):
                            if applied and message and not len(message) % 2:
                                print(
                                    "PASS: real voice handshake, settings and greeting PCM received. Browser playback still needs testing."
                                )
                                break
                        else:
                            event = json.loads(message)
                            if event.get("type") == "Welcome":
                                await socket.send(json.dumps(voice_settings(config)))
                            elif event.get("type") == "SettingsApplied":
                                applied = True
                            elif event.get("type") == "Error":
                                raise AppError(
                                    502,
                                    "voice_failed",
                                    "The real voice provider reported a session error.",
                                )
                    else:
                        raise AppError(
                            502,
                            "voice_closed",
                            "The real voice provider closed before returning audio.",
                        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except AppError as exc:
        print("FAIL: " + exc.message)
        raise SystemExit(1) from None
    except Exception:
        print(
            "FAIL: provider connection or configuration failed. Check server settings, key permissions and credits privately."
        )
        raise SystemExit(1) from None

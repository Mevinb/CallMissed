import asyncio
import base64
import binascii
import json
import httpx
from ..errors import AppError, upstream_error

API_BASE = "https://api.callmissed.com"
MAX_IMAGE_BYTES = 3_000_000


class CallMissed:
    def __init__(self, settings, client):
        self.settings, self.client = settings, client

    def headers(self):
        key = self.settings.callmissed_api_key.get_secret_value()
        if not key:
            raise AppError(
                503,
                "not_configured",
                "The app owner needs to configure the CallMissed API key on the server.",
            )
        return {"Authorization": "Bearer " + key}

    def safe_text(self, value):
        key = self.settings.callmissed_api_key.get_secret_value()
        return value.replace(key, "[redacted]") if key else value

    def payload(self, request):
        return {
            "model": self.settings.chat_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant in CallMissed AI Playground. Be clear, accurate and concise.",
                },
                *[m.model_dump() for m in request.messages],
            ],
            "max_tokens": 2048,
            "stream": request.stream,
        }

    async def post(self, path, payload, timeout=60):
        try:
            response = await self.client.post(
                API_BASE + path, headers=self.headers(), json=payload, timeout=timeout
            )
        except httpx.TimeoutException:
            raise AppError(
                504,
                "provider_timeout",
                "CallMissed took too long to respond. Please try again.",
            ) from None
        except httpx.RequestError:
            raise AppError(
                502,
                "provider_network",
                "Could not reach CallMissed. Please try again later.",
            ) from None
        if not response.is_success:
            raise upstream_error(response.status_code)
        try:
            return response.json()
        except ValueError:
            raise AppError(
                502, "provider_response", "CallMissed returned an unreadable response."
            ) from None

    async def chat(self, request):
        data = await self.post("/v1/chat/completions", self.payload(request))
        try:
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError()
            return {
                "content": self.safe_text(content),
                "model": self.settings.chat_model,
            }
        except (KeyError, IndexError, TypeError, ValueError):
            raise AppError(
                502, "provider_response", "CallMissed did not return a text answer."
            ) from None

    async def open_stream(self, request):
        headers = self.headers()
        req = self.client.build_request(
            "POST",
            API_BASE + "/v1/chat/completions",
            headers=headers,
            json=self.payload(request),
            timeout=60,
        )
        try:
            response = await self.client.send(req, stream=True)
        except httpx.TimeoutException:
            raise AppError(
                504,
                "provider_timeout",
                "CallMissed took too long to respond. Please try again.",
            ) from None
        except httpx.RequestError:
            raise AppError(502, "provider_network", "Could not reach CallMissed.") from None
        if not response.is_success:
            await response.aclose()
            raise upstream_error(response.status_code)
        if "text/event-stream" not in response.headers.get("content-type", ""):
            await response.aclose()
            raise AppError(502, "provider_response", "CallMissed did not return a chat stream.")
        return response

    async def stream(self, response):
        # Hold key-length characters across chunks so split secrets cannot escape.
        pending = ""
        key = self.settings.callmissed_api_key.get_secret_value()
        done = False
        saw_text = False
        try:
            async with asyncio.timeout(120):
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        done = True
                        break
                    data = json.loads(raw)
                    if data.get("error"):
                        raise ValueError("Upstream stream error")
                    choices = data.get("choices", [])
                    content = choices[0].get("delta", {}).get("content", "") if choices else ""
                    if not isinstance(content, str):
                        raise ValueError()
                    if content:
                        saw_text = True
                        pending = self.safe_text(pending + content)
                        hold = max(0, len(key) - 1)
                        emit, pending = (
                            (pending[:-hold], pending[-hold:])
                            if hold and len(pending) > hold
                            else ("", pending)
                        )
                        if not hold:
                            emit, pending = pending, ""
                        if emit:
                            yield self.event("token", {"content": emit})
            if not done or not saw_text:
                raise ValueError("Incomplete stream")
            if pending:
                yield self.event("token", {"content": self.safe_text(pending)})
            yield self.event("done", {"model": self.settings.chat_model})
        except (httpx.TimeoutException, TimeoutError):
            yield self.event("error", {"message": "The response timed out. Please try again."})
        except (httpx.RequestError, ValueError, TypeError, KeyError, IndexError):
            yield self.event(
                "error",
                {"message": "The response was interrupted or unreadable. Please try again."},
            )
        finally:
            await response.aclose()

    @staticmethod
    def event(name, data):
        return f"event: {name}\ndata: {json.dumps(data)}\n\n"

    async def image(self, request):
        data = await self.post(
            "/v1/images/generations",
            {
                "model": self.settings.image_model,
                "prompt": request.prompt,
                "n": 1,
                "size": request.size,
                "response_format": "b64_json",
            },
            timeout=180,
        )
        try:
            encoded = data["data"][0]["b64_json"]
            if not isinstance(encoded, str) or len(encoded) > MAX_IMAGE_BYTES * 4 / 3 + 8:
                raise ValueError()
            raw = base64.b64decode(encoded, validate=True)
            if len(raw) > MAX_IMAGE_BYTES:
                raise ValueError()
            if raw.startswith(b"\x89PNG\r\n\x1a\n"):
                mime = "image/png"
            elif raw.startswith(b"\xff\xd8\xff"):
                mime = "image/jpeg"
            else:
                raise ValueError()
            return {
                "b64_json": encoded,
                "mime_type": mime,
                "model": self.settings.image_model,
            }
        except (KeyError, IndexError, TypeError, ValueError, binascii.Error):
            raise AppError(
                502,
                "provider_image",
                "CallMissed returned an invalid image or one larger than this demo’s 3 MB limit.",
            ) from None

import hashlib
import hmac
import secrets
import time
from collections import OrderedDict
from itsdangerous import URLSafeTimedSerializer, BadSignature
from fastapi import Request
from .errors import AppError


class RateLimiter:
    """Atomic fixed windows in Redis; bounded memory fallback for one local worker."""

    def __init__(self, settings, client):
        self.settings, self.client = settings, client
        self.windows = OrderedDict()

    async def hit(self, identity: str, category: str, limit: int, seconds: int):
        bucket = int(time.time()) // seconds
        digest = hashlib.sha256(identity.encode()).hexdigest()[:32]
        key = f"callmissed:{category}:{digest}:{bucket}"
        if self.settings.upstash_redis_rest_url:
            script = "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n"
            try:
                response = await self.client.post(
                    self.settings.upstash_redis_rest_url,
                    headers={
                        "Authorization": "Bearer "
                        + self.settings.upstash_redis_rest_token.get_secret_value()
                    },
                    json=["EVAL", script, "1", key, str(seconds * 2)],
                    timeout=5,
                )
                response.raise_for_status()
                count = response.json()["result"]
                if not isinstance(count, int):
                    raise ValueError("Invalid Redis result")
            except Exception:
                raise AppError(
                    503,
                    "limits_unavailable",
                    "The access service is temporarily unavailable.",
                ) from None
        else:
            count = self.windows.get(key, 0) + 1
            self.windows[key] = count
            self.windows.move_to_end(key)
            while len(self.windows) > 10000:
                self.windows.popitem(last=False)
        if count > limit:
            raise AppError(
                429,
                "rate_limit",
                "You have reached the demo limit. Please try again later.",
            )


class Sessions:
    def __init__(self, settings):
        self.settings = settings
        self.signer = URLSafeTimedSerializer(
            settings.session_secret.get_secret_value(), salt="playground"
        )

    def issue(self):
        return self.signer.dumps({"id": secrets.token_urlsafe(24)})

    def verify(self, token):
        try:
            value = self.signer.loads(token or "", max_age=8 * 3600)
            return value["id"]
        except (BadSignature, KeyError, TypeError):
            raise AppError(401, "unauthorized", "Unlock the playground to continue.") from None

    def check_origin(self, origin):
        if origin not in self.settings.origins:
            raise AppError(403, "origin_denied", "This application origin is not allowed.")

    def login(self, code):
        expected = self.settings.demo_access_code.get_secret_value()
        if expected and not hmac.compare_digest(code.encode(), expected.encode()):
            raise AppError(401, "invalid_access_code", "The access code is incorrect.")
        return self.issue()


async def authorize(request: Request, category: str):
    state = request.app.state
    state.sessions.check_origin(request.headers.get("origin"))
    identity = state.sessions.verify(request.cookies.get("playground_session"))
    await state.limiter.hit(
        identity,
        category,
        {"chat": 20, "images": 3, "voice": 3}[category],
        3600 if category == "voice" else 60,
    )
    await state.limiter.hit("all", "daily", state.settings.global_daily_requests, 86400)
    return identity

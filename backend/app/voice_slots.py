import hashlib
import secrets
from .errors import AppError


# Both keys share a Redis hash tag. Admission, expiry cleanup and the global cap
# must run in one script; separate SET/INCR requests would permit races.
ACQUIRE = """
local now = tonumber(redis.call('TIME')[1])
redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now)
if redis.call('EXISTS', KEYS[1]) == 1 then return 0 end
if redis.call('ZCARD', KEYS[2]) >= tonumber(ARGV[3]) then return 0 end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
redis.call('ZADD', KEYS[2], now + tonumber(ARGV[2]), ARGV[1])
redis.call('EXPIRE', KEYS[2], ARGV[2])
return 1
"""
RELEASE = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  redis.call('DEL', KEYS[1])
end
return redis.call('ZREM', KEYS[2], ARGV[1])
"""


class VoiceSlots:
    """One call per session and four relays across all instances using Redis."""

    def __init__(self, settings, limiter, namespace="callmissed:{voice}"):
        self.settings, self.limiter, self.namespace = settings, limiter, namespace
        self.active = {}
        # Includes the 15s connection, 20s handshake and bounded socket cleanup.
        self.ttl = settings.voice_max_seconds + 60

    def keys(self, identity):
        digest = hashlib.sha256(identity.encode()).hexdigest()
        return [f"{self.namespace}:session:{digest}", f"{self.namespace}:active"]

    async def acquire(self, identity):
        token = secrets.token_urlsafe(24)
        if self.settings.upstash_redis_rest_url:
            admitted = await self.limiter.redis_command(
                ["EVAL", ACQUIRE, "2", *self.keys(identity), token, str(self.ttl), "4"]
            )
            if admitted not in (0, 1):
                raise AppError(503, "limits_unavailable", "The access service is unavailable.")
        else:
            admitted = identity not in self.active and len(self.active) < 4
            if admitted:
                self.active[identity] = token
        if not admitted:
            raise AppError(
                429,
                "voice_busy",
                "A voice conversation is already active or the demo is busy. Try again shortly.",
            )
        return token

    async def release(self, identity, token):
        if self.settings.upstash_redis_rest_url:
            await self.limiter.redis_command(["EVAL", RELEASE, "2", *self.keys(identity), token])
        elif self.active.get(identity) == token:
            del self.active[identity]

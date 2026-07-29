import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any, Optional
from uuid import uuid4

import redis.asyncio as aioredis
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class RedisService:
    """
    Redis service providing:
    - Idempotency key management
    - Rate limiting (sliding window)
    - Distributed locking (Redlock-style)
    - Session/cache storage
    """

    def __init__(self):
        self._client: Optional[aioredis.Redis] = None

    async def connect(self):
        self._client = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
            retry_on_timeout=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        await self._client.ping()
        logger.info("Redis connected", url=settings.REDIS_URL)

    async def disconnect(self):
        if self._client:
            await self._client.aclose()
        logger.info("Redis disconnected")

    @property
    def client(self) -> aioredis.Redis:
        if not self._client:
            raise RuntimeError("Redis not connected")
        return self._client

    # ─── Idempotency ──────────────────────────────────────────────────────────

    async def check_idempotency(self, key: str) -> Optional[dict]:
        """
        Check if a request with this idempotency key was already processed.
        Returns the cached response if found, None otherwise.
        """
        redis_key = f"idempotency:{key}"
        data = await self.client.get(redis_key)
        if data:
            logger.info("Idempotency cache hit", key=key)
            return json.loads(data)
        return None

    async def set_idempotency(self, key: str, response: dict, ttl: int = None):
        """Store the result for an idempotency key."""
        redis_key = f"idempotency:{key}"
        ttl = ttl or settings.REDIS_IDEMPOTENCY_TTL
        await self.client.setex(redis_key, ttl, json.dumps(response, default=str))
        logger.info("Idempotency key stored", key=key, ttl=ttl)

    # ─── Rate Limiting (Sliding Window) ───────────────────────────────────────

    async def check_rate_limit(
        self,
        identifier: str,
        limit: int,
        window_seconds: int = 60,
    ) -> tuple[bool, int, int]:
        """
        Sliding window rate limiter using Redis sorted sets.

        Returns: (is_allowed, current_count, retry_after_seconds)
        """
        now = asyncio.get_event_loop().time()
        window_start = now - window_seconds
        redis_key = f"rate_limit:{identifier}"

        pipe = self.client.pipeline()
        # Remove expired entries
        pipe.zremrangebyscore(redis_key, 0, window_start)
        # Count current requests in window
        pipe.zcard(redis_key)
        # Add current request
        pipe.zadd(redis_key, {str(uuid4()): now})
        # Set TTL
        pipe.expire(redis_key, window_seconds)
        results = await pipe.execute()

        current_count = results[1]

        if current_count >= limit:
            retry_after = int(window_seconds - (now - window_start))
            logger.warning(
                "Rate limit exceeded",
                identifier=identifier,
                count=current_count,
                limit=limit,
            )
            return False, current_count, max(retry_after, 1)

        return True, current_count + 1, 0

    # ─── Distributed Locking ─────────────────────────────────────────────────

    @asynccontextmanager
    async def distributed_lock(self, resource: str, ttl: int = 30):
        """
        Distributed lock using Redis SET NX (Redlock-style, single node).
        Use for preventing race conditions in payment processing.
        """
        lock_key = f"lock:{resource}"
        lock_value = str(uuid4())
        acquired = False

        try:
            acquired = await self.client.set(
                lock_key, lock_value, nx=True, ex=ttl
            )
            if not acquired:
                raise LockAcquisitionError(f"Could not acquire lock for {resource}")

            logger.debug("Lock acquired", resource=resource, ttl=ttl)
            yield

        finally:
            if acquired:
                # Only release if we own the lock (atomic check-and-delete via Lua)
                lua_script = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("del", KEYS[1])
                else
                    return 0
                end
                """
                await self.client.eval(lua_script, 1, lock_key, lock_value)
                logger.debug("Lock released", resource=resource)

    # ─── General Cache ────────────────────────────────────────────────────────

    async def get(self, key: str) -> Optional[Any]:
        data = await self.client.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return data
        return None

    async def set(self, key: str, value: Any, ttl: int = 3600):
        serialized = json.dumps(value, default=str) if not isinstance(value, str) else value
        await self.client.setex(key, ttl, serialized)

    async def delete(self, key: str):
        await self.client.delete(key)

    async def increment(self, key: str, ttl: int = 3600) -> int:
        pipe = self.client.pipeline()
        pipe.incr(key)
        pipe.expire(key, ttl)
        results = await pipe.execute()
        return results[0]

    # ─── Payment-specific helpers ─────────────────────────────────────────────

    async def get_merchant(self, merchant_id: str) -> Optional[dict]:
        return await self.get(f"merchant:{merchant_id}")

    async def cache_merchant(self, merchant_id: str, merchant_data: dict):
        await self.set(f"merchant:{merchant_id}", merchant_data, ttl=300)  # 5 min cache

    async def invalidate_merchant(self, merchant_id: str):
        await self.delete(f"merchant:{merchant_id}")


class LockAcquisitionError(Exception):
    pass


# Singleton instance
redis_service = RedisService()

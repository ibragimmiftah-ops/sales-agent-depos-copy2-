"""Short-term conversation memory backed by Redis with in-memory fallback."""

from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ShortTermMemory:
    """Stores the recent conversation history as a bounded list per conversation."""

    def __init__(self, redis_url: str | None = None):
        self._redis_url = redis_url or settings.REDIS_URL
        self._max_messages = settings.MAX_CONVERSATION_HISTORY
        self._ttl = settings.REDIS_SHORT_TERM_TTL_SECONDS
        self._redis: Any | None = None
        self._fallback: dict[str, list[dict[str, Any]]] = {}
        self._redis_available: bool | None = None

    def _key(self, conversation_id: str) -> str:
        return f"sa:conv:{conversation_id}:messages"

    async def _get_redis(self):
        if self._redis_available is False:
            return None
        if self._redis is not None:
            return self._redis
        try:
            from redis.asyncio import Redis
            self._redis = Redis.from_url(self._redis_url, decode_responses=True)
            await self._redis.ping()
            self._redis_available = True
            logger.info("redis_connected")
        except Exception as exc:
            logger.warning("redis_unavailable", error=str(exc))
            self._redis_available = False
            self._redis = None
        return self._redis

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        intent: str | None = None,
        decision: dict[str, Any] | None = None,
    ) -> None:
        entry = {
            "role": role,
            "content": content,
            "intent": intent,
            "decision": decision,
        }
        redis = await self._get_redis()
        if redis:
            await redis.rpush(self._key(conversation_id), json.dumps(entry, ensure_ascii=False))
            await redis.ltrim(self._key(conversation_id), -self._max_messages, -1)
            await redis.expire(self._key(conversation_id), self._ttl)
        else:
            hist = self._fallback.setdefault(conversation_id, [])
            hist.append(entry)
            if len(hist) > self._max_messages:
                hist.pop(0)

    async def get_messages(
        self, conversation_id: str, limit: int | None = None
    ) -> list[dict[str, Any]]:
        redis = await self._get_redis()
        if redis:
            raw = await redis.lrange(
                self._key(conversation_id), -(limit or self._max_messages), -1
            )
            messages = []
            for item in raw:
                try:
                    messages.append(json.loads(item))
                except json.JSONDecodeError:
                    continue
            return messages
        hist = self._fallback.get(conversation_id, [])
        if limit:
            return hist[-limit:]
        return hist.copy()

    async def clear(self, conversation_id: str) -> None:
        redis = await self._get_redis()
        if redis:
            await redis.delete(self._key(conversation_id))
        self._fallback.pop(conversation_id, None)

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from shared.config import Settings
from shared.redis_client import get_redis

LOGGER = logging.getLogger(__name__)


def _seconds_until_tomorrow() -> int:
    now = datetime.now()
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((tomorrow - now).total_seconds())


class QueryRateLimiter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _daily_key(self, user_id: str) -> str:
        return f"{self._settings.query_daily_key_prefix}{user_id}"

    def _error_key(self, user_id: str) -> str:
        return f"{self._settings.query_error_key_prefix}{user_id}"

    async def current_daily_count(self, user_id: str) -> int:
        try:
            redis = await get_redis()
            value = await redis.get(self._daily_key(user_id))
            return int(value) if value else 0
        except Exception:
            LOGGER.exception("redis current_daily_count failed")
            return 0

    async def increment_daily(self, user_id: str) -> int:
        try:
            redis = await get_redis()
            key = self._daily_key(user_id)
            count = await redis.incr(key)
            await redis.expire(key, _seconds_until_tomorrow())
            return int(count)
        except Exception:
            LOGGER.exception("redis increment_daily failed")
            return 0

    async def exceeds_daily_limit(self, user_id: str) -> bool:
        count = await self.current_daily_count(user_id)
        return count >= self._settings.query_daily_limit

    async def increment_error_template(self, user_id: str) -> int:
        try:
            redis = await get_redis()
            key = self._error_key(user_id)
            count = await redis.incr(key)
            await redis.expire(key, 7 * 24 * 3600)
            return int(count)
        except Exception:
            LOGGER.exception("redis increment_error_template failed")
            return 0

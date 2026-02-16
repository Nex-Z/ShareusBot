from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx

from shared.config import Settings

LOGGER = logging.getLogger(__name__)


class ShortUrlService:
    def __init__(self, settings: Settings) -> None:
        self._endpoint = settings.short_url_endpoint.strip()
        self._token = settings.short_url_token.strip().strip("'\"")
        self._use_bearer = settings.short_url_bearer

    @property
    def enabled(self) -> bool:
        return bool(self._endpoint and self._token)

    async def shorten(self, long_url: str) -> str:
        if not self.enabled:
            return long_url

        token_lower = self._token.lower()
        if token_lower.startswith("bearer ") or token_lower.startswith("token "):
            auth_value = self._token
        else:
            auth_value = f"Bearer {self._token}" if self._use_bearer else self._token
        headers = {
            "authorization": auth_value,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        payload = {
            "url": long_url,
            "expiry": (datetime.now() + timedelta(weeks = 1)).strftime("%Y-%m-%d"),
            "debrowser": {
                "type": "1",
                "app": "1,2",
            }
        }

        try:
            async with httpx.AsyncClient(timeout = 8, trust_env = False) as client:
                response = await client.post(
                    url = self._endpoint,
                    headers = headers,
                    json = payload,
                )
                response.raise_for_status()
                data = response.json()
                # 兼容两个常见字段
                short_url = data.get('short') or data.get("shortLink") or data.get("short_url") or data.get("url")
                return short_url or long_url
        except Exception:
            LOGGER.exception("short url request failed")
            return long_url

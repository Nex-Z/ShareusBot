from __future__ import annotations

import logging

import httpx

from shared.config import Settings

LOGGER = logging.getLogger(__name__)


class ShortUrlService:
    def __init__(self, settings: Settings) -> None:
        self._endpoint = settings.short_url_endpoint.strip()
        self._token = settings.short_url_token.strip()
        self._bearer = settings.short_url_bearer

    @property
    def enabled(self) -> bool:
        return bool(self._endpoint and self._token)

    async def shorten(self, long_url: str) -> str:
        if not self.enabled:
            return long_url

        headers = {"authorization": self._token}
        if self._bearer:
            headers = {"authorization": f"Bearer {self._token}"}

        payload = {"url": long_url}

        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.post(
                    self._endpoint,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                # 兼容两个常见字段
                short_url = data.get("shortLink") or data.get("short_url") or data.get("url")
                return short_url or long_url
        except Exception:
            LOGGER.exception("short url request failed")
            return long_url


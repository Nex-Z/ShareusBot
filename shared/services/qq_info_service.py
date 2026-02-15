from __future__ import annotations

import json

import httpx

from shared.config import Settings


class QQInfoService:
    def __init__(self, settings: Settings) -> None:
        self._api_base = settings.qq_info_api_url

    async def get_info(self, qq: str) -> tuple[str, str] | None:
        key = str(qq).strip()
        if not key or not self._api_base:
            return None

        url = f"{self._api_base}{key}"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url)
            if resp.status_code != 200 or not resp.text.strip():
                return None
        except Exception:
            return None

        data: dict
        try:
            data = resp.json()
        except Exception:
            try:
                data = json.loads(resp.text)
            except Exception:
                return None

        nickname = str(data.get("nickname") or data.get("name") or "").strip()
        avatar = str(data.get("headimg") or data.get("avatar") or "").strip()
        if not nickname and not avatar:
            return None
        return nickname, avatar


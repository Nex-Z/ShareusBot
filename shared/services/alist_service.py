from __future__ import annotations

import logging
import random
import string
from typing import Any

import httpx

from shared.config import Settings

LOGGER = logging.getLogger(__name__)


class AlistService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return bool(
            self._settings.alist_base_url
            and self._settings.alist_username
            and self._settings.alist_password
        )

    def _build_url(self, endpoint_or_url: str) -> str:
        value = (endpoint_or_url or "").strip()
        if value.startswith("http://") or value.startswith("https://"):
            return value
        if not value.startswith("/"):
            value = f"/{value}"
        return f"{self._settings.alist_base_url}{value}"

    def _generate_password(self, length: int = 8) -> str:
        pool = string.ascii_letters + string.digits
        return "".join(random.choice(pool) for _ in range(length))

    def _extract_token(self, payload: dict[str, Any]) -> str:
        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("token", "access_token", "jwt"):
                token = data.get(key)
                if token:
                    return str(token).strip()
        if isinstance(data, str) and data.strip():
            return data.strip()
        for key in ("token", "access_token", "jwt"):
            token = payload.get(key)
            if token:
                return str(token).strip()
        return ""

    async def _login(self) -> str:
        url = self._build_url(self._settings.alist_login_endpoint)
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(
                url,
                json={
                    "username": self._settings.alist_username,
                    "password": self._settings.alist_password,
                },
            )
            response.raise_for_status()
            token = self._extract_token(response.json())
            if not token:
                raise RuntimeError("Alist login succeeded but token is empty.")
            return token

    async def _get_meta(self, token: str) -> dict[str, Any]:
        url = self._build_url(self._settings.alist_meta_get_endpoint)
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get(
                url,
                params={"id": self._settings.alist_meta_id},
                headers={"authorization": token},
            )
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data")
            if isinstance(data, dict):
                return data
            raise RuntimeError("Alist meta get returned invalid payload.")

    async def _update_meta(self, token: str, data: dict[str, Any]) -> None:
        url = self._build_url(self._settings.alist_meta_update_endpoint)
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(
                url,
                json=data,
                headers={"authorization": token},
            )
            response.raise_for_status()

    def _default_refresh_path(self) -> str:
        prefix = self._settings.alist_r2_path_prefix.strip("/")
        if not prefix:
            return "/"
        return f"/{prefix}"

    async def refresh_fs_list(self, path: str | None = None) -> None:
        if not self.enabled:
            raise RuntimeError("Alist is not configured.")

        refresh_path = (path or "").strip() or self._default_refresh_path()
        url = self._build_url(self._settings.alist_fs_list_endpoint)
        token = await self._login()
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(
                url,
                json={
                    "path": refresh_path,
                    "password": "",
                    "page": 1,
                    "per_page": 10,
                    "refresh": True,
                },
                headers={"authorization": token},
            )
            response.raise_for_status()
            payload = response.json()
            code = payload.get("code")
            if code is not None:
                code_text = str(code).strip()
                if code_text not in {"0", "200"}:
                    message = payload.get("message") or payload.get("msg") or "unknown error"
                    raise RuntimeError(f"Alist fs list refresh failed: code={code_text}, message={message}")
        LOGGER.info("alist fs list refreshed: path=%s", refresh_path)

    async def reset_meta_password(self, password: str | None = None) -> str:
        if not self.enabled:
            raise RuntimeError("Alist is not configured.")

        final_password = (password or "").strip() or self._generate_password(8)
        token = await self._login()
        meta = await self._get_meta(token)
        meta["password"] = final_password
        await self._update_meta(token, meta)
        return final_password

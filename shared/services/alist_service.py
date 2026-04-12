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

    def _auth_headers(self, token: str) -> dict[str, str]:
        value = token.strip()
        if not value.lower().startswith("bearer "):
            value = f"Bearer {value}"
        return {"Authorization": value}

    def _assert_success(self, payload: Any, operation: str) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise RuntimeError(f"{operation} returned invalid payload type: {type(payload).__name__}")

        code = payload.get("code")
        if code is None:
            error = payload.get("error")
            if error:
                message = payload.get("message") or payload.get("msg") or error
                raise RuntimeError(f"{operation} failed: message={message}")
            if payload.get("success") is False:
                message = payload.get("message") or payload.get("msg") or "unknown error"
                raise RuntimeError(f"{operation} failed: message={message}")
            # 兼容只返回 token/data/ok 的接口
            return payload

        code_text = str(code).strip()
        if code_text not in {"0", "200"}:
            message = payload.get("message") or payload.get("msg") or "unknown error"
            raise RuntimeError(f"{operation} failed: code={code_text}, message={message}")
        return payload

    def _json_or_empty(self, response: httpx.Response, operation: str) -> dict[str, Any]:
        if not response.content:
            return {}
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(f"{operation} returned invalid JSON.") from exc
        return self._assert_success(payload, operation)

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
            payload = self._json_or_empty(response, "PanShow login")
            token = self._extract_token(payload)
            if not token:
                raise RuntimeError("PanShow login succeeded but token is empty.")
            return token

    def _directory_password_endpoint(self) -> str:
        endpoint = self._settings.alist_directory_password_endpoint.strip()
        if not endpoint:
            endpoint = "/api/admin/directory-passwords/{id}/password"
        try:
            return endpoint.format(id=self._settings.alist_directory_password_id)
        except KeyError as exc:
            raise RuntimeError(f"Unsupported directory password endpoint placeholder: {exc}") from exc

    async def _update_directory_password(self, token: str, password: str) -> None:
        url = self._build_url(self._directory_password_endpoint())
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.patch(
                url,
                json={"password": password},
                headers=self._auth_headers(token),
            )
            response.raise_for_status()
            self._json_or_empty(response, "PanShow directory password update")

    async def reset_meta_password(self, password: str | None = None) -> str:
        if not self.enabled:
            raise RuntimeError("Cloud disk is not configured.")

        final_password = (password or "").strip() or self._generate_password(8)
        token = await self._login()
        await self._update_directory_password(token, final_password)
        return final_password

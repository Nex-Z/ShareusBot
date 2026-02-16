from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.client import BaseClient
from botocore.config import Config

from shared.config import Settings


class R2Service:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._enabled = bool(
            settings.r2_endpoint
            and settings.r2_access_key
            and settings.r2_secret_key
            and settings.r2_bucket
        )
        self._client: BaseClient | None = None
        if self._enabled:
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.r2_endpoint,
                aws_access_key_id=settings.r2_access_key,
                aws_secret_access_key=settings.r2_secret_key,
                config=Config(signature_version="s3v4"),
            )

    @property
    def enabled(self) -> bool:
        return self._enabled and self._client is not None

    def _build_key(self, file_name: str) -> str:
        date_path = datetime.now().strftime("%Y/%m/%d")
        prefix = self._settings.r2_path_prefix.strip("/")
        if prefix:
            return f"{prefix}/{date_path}/{file_name}"
        return f"{date_path}/{file_name}"

    def _build_archive_url(self, key: str) -> str:
        base = (self._settings.alist_base_url or "").strip().rstrip("/")
        if not base:
            base = "https://pan.shareus.top"
        return f"{base}/{key.lstrip('/')}"

    async def upload(self, local_path: str, object_name: str | None = None) -> tuple[str, str]:
        if not self.enabled:
            raise RuntimeError("R2 is not configured.")

        target = Path(local_path)
        raw_name = (object_name or target.name or "").strip()
        target_name = Path(raw_name).name if raw_name else target.name
        key = self._build_key(target_name)

        def _run() -> None:
            self._client.upload_file(  # type: ignore[union-attr]
                str(target),
                self._settings.r2_bucket,
                key,
            )

        await asyncio.to_thread(_run)

        return key, self._build_archive_url(key)

    def _normalize_key(self, key_or_url: str) -> str:
        value = (key_or_url or "").strip()
        if not value:
            return ""
        if value.startswith("http://") or value.startswith("https://"):
            parsed = urlparse(value)
            return parsed.path.lstrip("/")
        return value.lstrip("/")

    async def delete(self, key_or_url: str) -> None:
        if not self.enabled:
            return
        key = self._normalize_key(key_or_url)
        if not key:
            return

        def _run() -> None:
            self._client.delete_object(  # type: ignore[union-attr]
                Bucket=self._settings.r2_bucket,
                Key=key,
            )

        await asyncio.to_thread(_run)

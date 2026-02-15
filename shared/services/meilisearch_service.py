from __future__ import annotations

import asyncio
import logging
from typing import Any

import meilisearch

from shared.config import Settings
from shared.models.archived_file import ArchivedFile

LOGGER = logging.getLogger(__name__)


class MeiliSearchService:
    def __init__(self, settings: Settings) -> None:
        self._enabled = bool(settings.meilisearch_host)
        self._index_name = settings.meilisearch_index
        self._client: meilisearch.Client | None = None
        if self._enabled:
            self._client = meilisearch.Client(
                settings.meilisearch_host,
                settings.meilisearch_api_key or None,
            )

    @property
    def enabled(self) -> bool:
        return self._enabled and self._client is not None

    def _index(self):
        if not self.enabled:
            raise RuntimeError("MeiliSearch is not configured.")
        return self._client.index(self._index_name)  # type: ignore[union-attr]

    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        if not self.enabled:
            return []

        def _run() -> list[dict[str, Any]]:
            result = self._index().search(
                query,
                {
                    "limit": limit,
                    "sort": ["archiveDate:desc"],
                    "attributesToSearchOn": ["name"],
                    "filter": "enabled = 0",
                },
            )
            return list(result.get("hits", []))

        try:
            return await asyncio.to_thread(_run)
        except Exception:
            LOGGER.exception("MeiliSearch query failed: %s", query)
            return []

    async def index_archived_file(self, item: ArchivedFile) -> None:
        if not self.enabled:
            return

        doc = {
            "id": item.id,
            "name": item.name,
            "senderId": item.sender_id,
            "size": item.size,
            "md5": item.md5,
            "enabled": item.enabled,
            "delFlag": item.del_flag,
            "originUrl": item.origin_url,
            "archiveUrl": item.archive_url,
            "archiveDate": item.archive_date.isoformat(),
        }

        def _run() -> None:
            self._index().add_documents([doc], primary_key = "id")

        try:
            await asyncio.to_thread(_run)
        except Exception:
            LOGGER.exception("MeiliSearch index failed for archive_id=%s", item.id)

from __future__ import annotations

import random

import httpx
from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.config import Settings
from shared.models.nonsense import Nonsense


class NonsenseService:
    _fallback_content = [
        "Take a break and share something useful today.",
        "A small share can help many people find what they need.",
        "Keep learning, keep sharing, keep improving.",
    ]

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._api_url = settings.nonsense_api_url
        self._max_request_times = max(1, settings.nonsense_max_request_times)
        self._blocked_words = [w.lower() for w in settings.ban_words if w.strip()]

    def _is_blocked(self, content: str) -> bool:
        raw = content.lower()
        return any(word in raw for word in self._blocked_words)

    async def _fetch_remote(self) -> str:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(self._api_url)
            resp.raise_for_status()
            return resp.text.strip()

    async def _record_send(self, content: str) -> None:
        if not content:
            return
        async with self._session_factory() as session:
            stmt = select(Nonsense).where(Nonsense.content == content).limit(1)
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                row = Nonsense(content=content, send_times=1)
                session.add(row)
            else:
                row.send_times = int(row.send_times or 0) + 1
            await session.commit()

    async def _pick_from_db(self) -> str:
        async with self._session_factory() as session:
            stmt = (
                select(Nonsense)
                .where(Nonsense.content != "")
                .order_by(asc(Nonsense.send_times), asc(Nonsense.update_time))
                .limit(10)
            )
            rows = list((await session.execute(stmt)).scalars().all())
            if not rows:
                return ""
            return (random.choice(rows).content or "").strip()

    async def get_for_send(self) -> str:
        content = ""
        for _ in range(self._max_request_times):
            try:
                candidate = await self._fetch_remote()
            except Exception:
                break
            if not candidate or self._is_blocked(candidate):
                continue
            content = candidate
            break

        if not content:
            candidate = await self._pick_from_db()
            if candidate and not self._is_blocked(candidate):
                content = candidate

        if not content:
            safe_fallback = [c for c in self._fallback_content if not self._is_blocked(c)]
            content = random.choice(safe_fallback or self._fallback_content).strip()

        await self._record_send(content)
        return content


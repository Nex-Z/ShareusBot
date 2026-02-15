from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.models.archived_file import ArchivedFile


class ArchiveService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_md5(self, md5: str) -> ArchivedFile | None:
        async with self._session_factory() as session:
            stmt = select(ArchivedFile).where(ArchivedFile.md5 == md5).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def search_by_name(self, keyword: str, limit: int = 10) -> list[ArchivedFile]:
        async with self._session_factory() as session:
            stmt = (
                select(ArchivedFile)
                .where(
                    ArchivedFile.enabled == 0,
                    ArchivedFile.name.like(f"%{keyword}%"),
                )
                .order_by(desc(ArchivedFile.archive_date))
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def count_between(self, start: datetime, end: datetime) -> int:
        async with self._session_factory() as session:
            stmt = select(func.count()).where(
                ArchivedFile.archive_date >= start,
                ArchivedFile.archive_date < end,
            )
            result = await session.execute(stmt)
            return int(result.scalar() or 0)

    async def top_senders_between(
        self,
        start: datetime,
        end: datetime,
        limit: int = 5,
    ) -> list[tuple[str, int]]:
        async with self._session_factory() as session:
            stmt = (
                select(ArchivedFile.sender_id, func.count().label("cnt"))
                .where(
                    ArchivedFile.archive_date >= start,
                    ArchivedFile.archive_date < end,
                )
                .group_by(ArchivedFile.sender_id)
                .order_by(desc("cnt"))
                .limit(limit)
            )
            rows = (await session.execute(stmt)).all()
            return [(str(row[0]), int(row[1])) for row in rows]

    async def list_distinct_sender_ids(self) -> list[str]:
        async with self._session_factory() as session:
            stmt = (
                select(ArchivedFile.sender_id)
                .where(ArchivedFile.sender_id != "")
                .group_by(ArchivedFile.sender_id)
            )
            rows = (await session.execute(stmt)).all()
            return [str(row[0]) for row in rows]

    async def save_archive(
        self,
        file_name: str,
        archive_url: str,
        sender_id: str,
        group_id: str,
        file_size: int,
        file_type: str,
        md5: str = "",
        origin_url: str = "",
        enabled: int = 0,
    ) -> ArchivedFile:
        async with self._session_factory() as session:
            item = ArchivedFile(
                name=file_name,
                archive_url=archive_url,
                archive_date=datetime.now(),
                sender_id=str(sender_id),
                group_id=str(group_id),
                file_size=file_size,
                file_type=file_type,
                md5=md5,
                origin_url=origin_url,
                enabled=enabled,
            )
            session.add(item)
            await session.commit()
            await session.refresh(item)
            return item

from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.models.archived_file import ArchivedFile


class ArchiveService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_md5(self, md5: str) -> ArchivedFile | None:
        async with self._session_factory() as session:
            stmt = (
                select(ArchivedFile)
                .where(
                    ArchivedFile.md5 == md5,
                    ArchivedFile.del_flag == 0,
                )
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def search_by_name(self, keyword: str, limit: int = 10) -> list[ArchivedFile]:
        async with self._session_factory() as session:
            stmt = (
                select(ArchivedFile)
                .where(
                    ArchivedFile.enabled == 0,
                    ArchivedFile.del_flag == 0,
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
                    ArchivedFile.del_flag == 0,
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
                .where(
                    ArchivedFile.sender_id.is_not(None),
                    ArchivedFile.del_flag == 0,
                )
                .group_by(ArchivedFile.sender_id)
            )
            rows = (await session.execute(stmt)).all()
            return [str(row[0]) for row in rows]

    async def save_archive(
        self,
        file_name: str,
        archive_url: str,
        sender_id: str,
        size: int,
        md5: str = "",
        origin_url: str = "",
        enabled: int = 0,
    ) -> ArchivedFile:
        async with self._session_factory() as session:
            item = ArchivedFile(
                id=uuid.uuid4().hex,
                name=file_name,
                sender_id=int(sender_id),
                size=size,
                md5=md5,
                enabled=int(enabled),
                del_flag=0,
                origin_url=origin_url,
                archive_url=archive_url,
                archive_date=datetime.now(),
            )
            session.add(item)
            await session.commit()
            await session.refresh(item)
            return item

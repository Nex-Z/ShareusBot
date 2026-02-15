from __future__ import annotations

from datetime import datetime
import json

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.models.query_log import QueryLog


class QueryLogService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def record_query(
        self,
        *,
        content: str,
        extract: str,
        sender_id: str,
        sender_name: str,
        send_time: datetime,
        result_rows: list[dict],
    ) -> QueryLog:
        has_result = bool(result_rows)
        item = QueryLog(
            content=content,
            extract=extract,
            sender_id=int(sender_id),
            sender_name=sender_name or "",
            send_time=send_time,
            status=0 if has_result else 1,
            result=json.dumps(result_rows, ensure_ascii=False) if has_result else "",
            answer_id=0,
            finish_time=datetime.now() if has_result else None,
        )
        async with self._session_factory() as session:
            session.add(item)
            await session.commit()
            await session.refresh(item)
            return item

    async def close_pending_by_archive(
        self,
        *,
        archive_name: str,
        archive_url: str,
    ) -> int:
        async with self._session_factory() as session:
            stmt = select(QueryLog).where(QueryLog.status == 1)
            rows = list((await session.execute(stmt)).scalars().all())

            updated = 0
            now = datetime.now()
            for row in rows:
                extract = (row.extract or "").strip()
                if not extract:
                    continue
                if extract not in archive_name:
                    continue
                row.status = 0
                row.finish_time = now
                row.answer_id = 0
                row.result = json.dumps(
                    [{"name": archive_name, "archive_url": archive_url}],
                    ensure_ascii=False,
                )
                updated += 1

            if updated > 0:
                await session.commit()
            return updated

    async def count_between(self, start: datetime, end: datetime) -> int:
        async with self._session_factory() as session:
            stmt = select(func.count()).where(
                QueryLog.send_time >= start,
                QueryLog.send_time < end,
            )
            result = await session.execute(stmt)
            return int(result.scalar() or 0)

    async def count_unfinished(self) -> int:
        async with self._session_factory() as session:
            stmt = select(func.count()).where(QueryLog.status == 1)
            result = await session.execute(stmt)
            return int(result.scalar() or 0)

    async def list_unfinished(self, limit: int = 500) -> list[QueryLog]:
        async with self._session_factory() as session:
            stmt = (
                select(QueryLog)
                .where(QueryLog.status == 1)
                .order_by(desc(QueryLog.send_time))
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return list(rows)

    async def list_unfinished_older_than(self, before: datetime, limit: int = 200) -> list[QueryLog]:
        async with self._session_factory() as session:
            stmt = (
                select(QueryLog)
                .where(
                    QueryLog.status == 1,
                    QueryLog.send_time < before,
                )
                .order_by(QueryLog.send_time.asc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return list(rows)

    async def mark_finished(self, query_log_id: int, result_rows: list[dict]) -> bool:
        async with self._session_factory() as session:
            stmt = select(QueryLog).where(QueryLog.id == query_log_id).limit(1)
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return False
            row.status = 0
            row.finish_time = datetime.now()
            row.answer_id = 0
            row.result = json.dumps(result_rows, ensure_ascii=False)
            await session.commit()
            return True

    async def mark_closed(self, query_log_id: int, reason: str) -> bool:
        async with self._session_factory() as session:
            stmt = select(QueryLog).where(QueryLog.id == query_log_id).limit(1)
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return False
            row.status = 2
            row.finish_time = datetime.now()
            row.result = reason
            await session.commit()
            return True

    async def top_extract_between(
        self,
        start: datetime,
        end: datetime,
        limit: int = 10,
    ) -> list[tuple[str, int]]:
        async with self._session_factory() as session:
            stmt = (
                select(QueryLog.extract, func.count().label("cnt"))
                .where(
                    QueryLog.send_time >= start,
                    QueryLog.send_time < end,
                    QueryLog.extract != "",
                )
                .group_by(QueryLog.extract)
                .order_by(desc("cnt"))
                .limit(limit)
            )
            rows = (await session.execute(stmt)).all()
            return [(str(row[0]), int(row[1])) for row in rows]

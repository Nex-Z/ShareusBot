from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.models.black_list import BlackList


class BlackListService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_qq(self, qq_id: str) -> BlackList | None:
        async with self._session_factory() as session:
            stmt = select(BlackList).where(BlackList.qq_id == str(qq_id)).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_all(self) -> list[BlackList]:
        async with self._session_factory() as session:
            stmt = select(BlackList)
            rows = (await session.execute(stmt)).scalars().all()
            return list(rows)

    async def add(
        self,
        qq_id: str,
        nick_name: str,
        remark: str,
        create_by: str,
        create_by_id: str,
    ) -> BlackList | None:
        async with self._session_factory() as session:
            exists_stmt = select(BlackList).where(BlackList.qq_id == str(qq_id)).limit(1)
            exists = (await session.execute(exists_stmt)).scalar_one_or_none()
            if exists is not None:
                return None

            item = BlackList(
                qq_id=str(qq_id),
                nick_name=nick_name or "",
                remark=remark or "",
                create_by=create_by or "",
                create_by_id=str(create_by_id),
            )
            session.add(item)
            await session.commit()
            await session.refresh(item)
            return item

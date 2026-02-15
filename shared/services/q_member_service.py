from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.models.q_member import QMember


class QMemberService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_all(self) -> list[QMember]:
        async with self._session_factory() as session:
            stmt = select(QMember)
            rows = (await session.execute(stmt)).scalars().all()
            return list(rows)

    async def upsert_many(self, records: list[tuple[str, str, str]]) -> tuple[int, int]:
        if not records:
            return 0, 0

        qq_values = sorted({str(item[0]).strip() for item in records if str(item[0]).strip()})
        if not qq_values:
            return 0, 0

        async with self._session_factory() as session:
            exists_stmt = select(QMember).where(QMember.qq.in_(qq_values))
            exists_rows = (await session.execute(exists_stmt)).scalars().all()
            exists_map = {str(row.qq): row for row in exists_rows}

            updated = 0
            created = 0
            for qq, nick_name, avatar_url in records:
                key = str(qq).strip()
                if not key:
                    continue
                nick = (nick_name or "").strip()
                avatar = (avatar_url or "").strip()
                row = exists_map.get(key)
                if row is None:
                    row = QMember(qq=key, nick_name=nick, avatar_url=avatar)
                    session.add(row)
                    exists_map[key] = row
                    created += 1
                    continue
                changed = False
                if nick and row.nick_name != nick:
                    row.nick_name = nick
                    changed = True
                if avatar and row.avatar_url != avatar:
                    row.avatar_url = avatar
                    changed = True
                if changed:
                    updated += 1

            await session.commit()
            return updated, created


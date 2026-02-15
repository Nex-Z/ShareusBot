from __future__ import annotations

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base, TimestampMixin


class QMember(Base, TimestampMixin):
    __tablename__ = "q_member"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    qq: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    nick_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    avatar_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")


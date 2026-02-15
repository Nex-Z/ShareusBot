from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class QMember(Base):
    __tablename__ = "q_member"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    qq: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    nick_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    avatar_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    special_title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    remark: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    del_flag: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    create_by: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    create_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    update_by: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

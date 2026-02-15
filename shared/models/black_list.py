from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class BlackList(Base):
    __tablename__ = "black_list"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    qq_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    nick_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    remark: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    del_flag: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    create_by: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    create_by_id: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    create_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

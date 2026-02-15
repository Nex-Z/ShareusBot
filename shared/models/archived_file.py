from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class ArchivedFile(Base):
    __tablename__ = "archived_file"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    sender_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    md5: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    del_flag: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    origin_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    archive_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    archive_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

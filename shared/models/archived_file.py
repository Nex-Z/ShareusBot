from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base, TimestampMixin


class ArchivedFile(Base, TimestampMixin):
    __tablename__ = "archived_file"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    archive_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    archive_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sender_id: Mapped[str] = mapped_column(String(32), nullable=False)
    group_id: Mapped[str] = mapped_column(String(32), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    file_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    md5: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    origin_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    enabled: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


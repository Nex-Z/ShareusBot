from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class QueryLog(Base):
    __tablename__ = "query_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    extract: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    sender_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sender_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    send_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    result: Mapped[str] = mapped_column(Text, nullable=False, default="")
    answer_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    finish_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

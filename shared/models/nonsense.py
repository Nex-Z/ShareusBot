from __future__ import annotations

from sqlalchemy import BigInteger, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base, TimestampMixin


class Nonsense(Base, TimestampMixin):
    __tablename__ = "nonsense"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    send_times: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


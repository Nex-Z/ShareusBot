from __future__ import annotations

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base, TimestampMixin


class BlackList(Base, TimestampMixin):
    __tablename__ = "black_list"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    qq_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    nick_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    remark: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    create_by: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    create_by_id: Mapped[str] = mapped_column(String(32), nullable=False, default="")


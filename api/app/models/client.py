import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ClientStatus(str, PyEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    GRADUATED = "graduated"
    TRANSFERRED = "transferred"


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    code_name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "A-兜兜"
    display_alias: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "兜兜"
    status: Mapped[str] = mapped_column(String(50), default=ClientStatus.ACTIVE.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ClientUserLink(Base):
    __tablename__ = "client_user_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    relation: Mapped[str] = mapped_column(String(50), nullable=False)  # "teacher" | "parent"

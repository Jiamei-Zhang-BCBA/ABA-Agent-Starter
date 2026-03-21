import uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, Text, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    features_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    max_clients: Mapped[int] = mapped_column(Integer, default=5)
    max_staff: Mapped[int] = mapped_column(Integer, default=3)
    monthly_jobs: Mapped[int] = mapped_column(Integer, default=100)
    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    tenants: Mapped[list["Tenant"]] = relationship(back_populates="plan")


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("plans.id"), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    plan: Mapped["Plan"] = relationship(back_populates="tenants", lazy="joined")
    users: Mapped[list["User"]] = relationship(back_populates="tenant")  # noqa: F821

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class RenewalFrequency(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class RouteCategory(str, Enum):
    public = "public"
    standard = "standard"
    premium = "premium"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    permissions: Mapped[list["RolePermission"]] = relationship("RolePermission", cascade="all, delete-orphan")


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(120), nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    role: Mapped[Role] = relationship("Role")
    organization: Mapped[Organization] = relationship("Organization")


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    org_id: Mapped[Optional[int]] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    rate_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    rate_window_secs: Mapped[int] = mapped_column(Integer, nullable=False)
    credit_cost_multiplier: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    renewal_frequency: Mapped[str] = mapped_column(String(20), default=RenewalFrequency.monthly.value, nullable=False)
    base_credits: Mapped[float] = mapped_column(Float, nullable=False)
    valid_days: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), nullable=False)
    credit_balance: Mapped[float] = mapped_column(Float, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped[User] = relationship("User")
    plan: Mapped[Plan] = relationship("Plan")


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    path_pattern: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    base_credit_cost: Mapped[float] = mapped_column(Float, nullable=False)
    base_rate_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    base_rate_window_secs: Mapped[int] = mapped_column(Integer, nullable=False)
    upstream_url: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    api_key_id: Mapped[int] = mapped_column(ForeignKey("api_keys.id"), nullable=False)
    delta: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    balance_after: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    api_key_id: Mapped[int] = mapped_column(ForeignKey("api_keys.id"), nullable=False)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    credits_charged: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    target_table: Mapped[str] = mapped_column(String(120), nullable=False)
    target_id: Mapped[str] = mapped_column(String(120), nullable=False)
    before: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    after: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

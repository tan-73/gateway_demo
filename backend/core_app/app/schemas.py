from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TokenRequest(BaseModel):
    api_key: str


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str


class BootstrapStatusResponse(BaseModel):
    admin_email: str
    admin_password_configured: bool
    seeded_keys_available: bool


class OrganizationCreate(BaseModel):
    name: str


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    created_at: datetime


class RoleCreate(BaseModel):
    name: str
    permissions: List[str] = Field(default_factory=list)


class RolePermissionsPatch(BaseModel):
    permissions: List[str]


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    permissions: List[str]


class UserCreate(BaseModel):
    email: str
    role_id: int
    org_id: int


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    role_id: int
    org_id: int
    created_at: datetime


class PlanBase(BaseModel):
    name: str
    org_id: Optional[int] = None
    rate_limit: int
    rate_window_secs: int
    credit_cost_multiplier: float
    renewal_frequency: str
    base_credits: float
    valid_days: int
    active: bool = True


class PlanCreate(PlanBase):
    pass


class PlanPatch(BaseModel):
    name: Optional[str] = None
    org_id: Optional[int] = None
    rate_limit: Optional[int] = None
    rate_window_secs: Optional[int] = None
    credit_cost_multiplier: Optional[float] = None
    renewal_frequency: Optional[str] = None
    base_credits: Optional[float] = None
    valid_days: Optional[int] = None
    active: Optional[bool] = None


class PlanRead(PlanBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class RouteBase(BaseModel):
    path_pattern: str
    method: str
    category: str
    base_credit_cost: float
    base_rate_limit: int
    base_rate_window_secs: int
    upstream_url: str
    active: bool = True


class RouteCreate(RouteBase):
    pass


class RoutePatch(BaseModel):
    path_pattern: Optional[str] = None
    method: Optional[str] = None
    category: Optional[str] = None
    base_credit_cost: Optional[float] = None
    base_rate_limit: Optional[int] = None
    base_rate_window_secs: Optional[int] = None
    upstream_url: Optional[str] = None
    active: Optional[bool] = None


class RouteRead(RouteBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ApiKeyCreate(BaseModel):
    user_id: int
    plan_id: int
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    active: bool = True


class ApiKeyPatch(BaseModel):
    plan_id: Optional[int] = None
    credit_balance: Optional[float] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    active: Optional[bool] = None


class ApiKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    plan_id: int
    credit_balance: float
    valid_from: datetime
    valid_until: datetime
    active: bool
    created_at: datetime


class ApiKeyCreateResponse(BaseModel):
    api_key: str
    record: ApiKeyRead


class CreditLedgerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    api_key_id: int
    delta: float
    reason: str
    balance_after: float
    created_at: datetime


class UsageLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    api_key_id: int
    route_id: int
    status_code: int
    latency_ms: float
    credits_charged: float
    created_at: datetime


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    actor_user_id: Optional[int]
    action: str
    target_table: str
    target_id: str
    before: Optional[Dict[str, Any]]
    after: Optional[Dict[str, Any]]
    created_at: datetime


class MeBalanceRead(BaseModel):
    api_key_id: int
    credit_balance: float
    plan_name: str
    valid_from: datetime
    valid_until: datetime

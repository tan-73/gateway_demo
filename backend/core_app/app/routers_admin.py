from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .dependencies import get_config_store, get_current_identity
from .models import ApiKey, AuditLog, CreditTransaction, Organization, Plan, Role, RolePermission, Route, UsageLog, User
from .schemas import (
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyPatch,
    ApiKeyRead,
    AuditLogRead,
    CreditLedgerRead,
    OrganizationCreate,
    OrganizationRead,
    PlanCreate,
    PlanPatch,
    PlanRead,
    RoleCreate,
    RolePermissionsPatch,
    RoleRead,
    RouteCreate,
    RoutePatch,
    RouteRead,
    UsageLogRead,
    UserCreate,
    UserRead,
)
from .services import ConfigStore, apply_credit_change, audit, create_api_key_record, enforce_org_scope, enforce_permission, model_to_dict

router = APIRouter(prefix="/admin", tags=["admin"])


def admin_identity(identity=Depends(get_current_identity)):
    return identity


@router.get("/organizations", response_model=list[OrganizationRead])
def list_organizations(identity=Depends(admin_identity), db: Session = Depends(get_db)):
    enforce_permission(identity["user"], "organizations:read")
    query = select(Organization)
    if identity["user"].role.name == "org_admin":
        query = query.where(Organization.id == identity["user"].org_id)
    return db.execute(query).scalars().all()


@router.post("/organizations", response_model=OrganizationRead)
def create_organization(payload: OrganizationCreate, identity=Depends(admin_identity), db: Session = Depends(get_db)):
    enforce_permission(identity["user"], "organizations:write")
    org = Organization(name=payload.name)
    db.add(org)
    db.flush()
    audit(db, identity["user"].id, "create", "organizations", str(org.id), None, model_to_dict(org, ["id", "name"]))
    db.commit()
    return org


@router.get("/users", response_model=list[UserRead])
def list_users(identity=Depends(admin_identity), db: Session = Depends(get_db)):
    enforce_permission(identity["user"], "users:read")
    query = select(User)
    if identity["user"].role.name == "org_admin":
        query = query.where(User.org_id == identity["user"].org_id)
    return db.execute(query).scalars().all()


@router.post("/users", response_model=UserRead)
def create_user(payload: UserCreate, identity=Depends(admin_identity), db: Session = Depends(get_db)):
    enforce_permission(identity["user"], "users:write")
    enforce_org_scope(identity["user"], payload.org_id)
    user = User(email=payload.email, role_id=payload.role_id, org_id=payload.org_id)
    db.add(user)
    db.flush()
    audit(db, identity["user"].id, "create", "users", str(user.id), None, model_to_dict(user, ["id", "email", "role_id", "org_id"]))
    db.commit()
    return user


@router.get("/roles", response_model=list[RoleRead])
def list_roles(identity=Depends(admin_identity), db: Session = Depends(get_db)):
    enforce_permission(identity["user"], "roles:read")
    roles = db.execute(select(Role)).scalars().all()
    return [RoleRead(id=role.id, name=role.name, permissions=[perm.permission for perm in role.permissions]) for role in roles]


@router.post("/roles", response_model=RoleRead)
def create_role(payload: RoleCreate, identity=Depends(admin_identity), db: Session = Depends(get_db)):
    enforce_permission(identity["user"], "roles:write")
    role = Role(name=payload.name)
    db.add(role)
    db.flush()
    for permission in payload.permissions:
        db.add(RolePermission(role_id=role.id, permission=permission))
    db.flush()
    audit(db, identity["user"].id, "create", "roles", str(role.id), None, {"name": role.name, "permissions": payload.permissions})
    db.commit()
    return RoleRead(id=role.id, name=role.name, permissions=payload.permissions)


@router.patch("/roles/{role_id}/permissions", response_model=RoleRead)
def patch_role_permissions(role_id: int, payload: RolePermissionsPatch, identity=Depends(admin_identity), db: Session = Depends(get_db)):
    enforce_permission(identity["user"], "roles:write")
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    before = [perm.permission for perm in role.permissions]
    for perm in list(role.permissions):
        db.delete(perm)
    db.flush()
    for permission in payload.permissions:
        db.add(RolePermission(role_id=role.id, permission=permission))
    db.flush()
    audit(db, identity["user"].id, "patch", "roles", str(role.id), {"permissions": before}, {"permissions": payload.permissions})
    db.commit()
    return RoleRead(id=role.id, name=role.name, permissions=payload.permissions)


@router.get("/plans", response_model=list[PlanRead])
def list_plans(identity=Depends(admin_identity), db: Session = Depends(get_db)):
    enforce_permission(identity["user"], "plans:read")
    query = select(Plan)
    if identity["user"].role.name == "org_admin":
        query = query.where((Plan.org_id == identity["user"].org_id) | (Plan.org_id.is_(None)))
    return db.execute(query).scalars().all()


@router.post("/plans", response_model=PlanRead)
def create_plan(payload: PlanCreate, identity=Depends(admin_identity), db: Session = Depends(get_db), config_store: ConfigStore = Depends(get_config_store)):
    enforce_permission(identity["user"], "plans:write")
    enforce_org_scope(identity["user"], payload.org_id)
    plan = Plan(**payload.model_dump())
    db.add(plan)
    db.flush()
    audit(db, identity["user"].id, "create", "plans", str(plan.id), None, payload.model_dump())
    db.commit()
    config_store.invalidate("key:")
    return plan


@router.patch("/plans/{plan_id}", response_model=PlanRead)
def patch_plan(plan_id: int, payload: PlanPatch, identity=Depends(admin_identity), db: Session = Depends(get_db), config_store: ConfigStore = Depends(get_config_store)):
    enforce_permission(identity["user"], "plans:write")
    plan = db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    enforce_org_scope(identity["user"], plan.org_id)
    before = model_to_dict(plan, ["name", "org_id", "rate_limit", "rate_window_secs", "credit_cost_multiplier", "renewal_frequency", "base_credits", "valid_days", "active"])
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, key, value)
    db.flush()
    audit(db, identity["user"].id, "patch", "plans", str(plan.id), before, payload.model_dump(exclude_unset=True))
    db.commit()
    config_store.invalidate("key:")
    return plan


@router.get("/routes", response_model=list[RouteRead])
def list_routes(identity=Depends(admin_identity), db: Session = Depends(get_db)):
    enforce_permission(identity["user"], "routes:read")
    return db.execute(select(Route)).scalars().all()


@router.post("/routes", response_model=RouteRead)
def create_route(payload: RouteCreate, identity=Depends(admin_identity), db: Session = Depends(get_db), config_store: ConfigStore = Depends(get_config_store)):
    enforce_permission(identity["user"], "routes:write")
    route = Route(**payload.model_dump())
    db.add(route)
    db.flush()
    audit(db, identity["user"].id, "create", "routes", str(route.id), None, payload.model_dump())
    db.commit()
    config_store.invalidate("route:")
    return route


@router.patch("/routes/{route_id}", response_model=RouteRead)
def patch_route(route_id: int, payload: RoutePatch, identity=Depends(admin_identity), db: Session = Depends(get_db), config_store: ConfigStore = Depends(get_config_store)):
    enforce_permission(identity["user"], "routes:write")
    route = db.get(Route, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    before = model_to_dict(route, ["path_pattern", "method", "category", "base_credit_cost", "base_rate_limit", "base_rate_window_secs", "upstream_url", "active"])
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(route, key, value)
    db.flush()
    audit(db, identity["user"].id, "patch", "routes", str(route.id), before, payload.model_dump(exclude_unset=True))
    db.commit()
    config_store.invalidate("route:")
    return route


@router.get("/api-keys", response_model=list[ApiKeyRead])
def list_api_keys(identity=Depends(admin_identity), db: Session = Depends(get_db)):
    enforce_permission(identity["user"], "keys:read")
    query = select(ApiKey).join(User)
    if identity["user"].role.name == "org_admin":
        query = query.where(User.org_id == identity["user"].org_id)
    return db.execute(query).scalars().all()


@router.post("/api-keys", response_model=ApiKeyCreateResponse)
def create_api_key(payload: ApiKeyCreate, identity=Depends(admin_identity), db: Session = Depends(get_db), config_store: ConfigStore = Depends(get_config_store)):
    enforce_permission(identity["user"], "keys:write")
    user = db.get(User, payload.user_id)
    plan = db.get(Plan, payload.plan_id)
    if not user or not plan:
        raise HTTPException(status_code=404, detail="User or plan not found")
    enforce_org_scope(identity["user"], user.org_id)
    raw, record = create_api_key_record(db, user.id, plan, payload.valid_from, payload.valid_until, payload.active)
    db.flush()
    audit(db, identity["user"].id, "create", "api_keys", str(record.id), None, {"user_id": user.id, "plan_id": plan.id})
    db.commit()
    config_store.invalidate("key:")
    return ApiKeyCreateResponse(api_key=raw, record=record)


@router.patch("/api-keys/{api_key_id}", response_model=ApiKeyRead)
def patch_api_key(api_key_id: int, payload: ApiKeyPatch, identity=Depends(admin_identity), db: Session = Depends(get_db), config_store: ConfigStore = Depends(get_config_store)):
    enforce_permission(identity["user"], "keys:write")
    record = db.get(ApiKey, api_key_id)
    if not record:
        raise HTTPException(status_code=404, detail="API key not found")
    user = db.get(User, record.user_id)
    enforce_org_scope(identity["user"], user.org_id)
    before = model_to_dict(record, ["plan_id", "credit_balance", "valid_from", "valid_until", "active"])
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    db.flush()
    audit(db, identity["user"].id, "patch", "api_keys", str(record.id), before, payload.model_dump(exclude_unset=True))
    db.commit()
    config_store.invalidate("key:")
    return record


@router.get("/usage-logs", response_model=list[UsageLogRead])
def list_usage_logs(
    identity=Depends(admin_identity),
    db: Session = Depends(get_db),
    api_key_id: Optional[int] = Query(default=None),
    route_id: Optional[int] = Query(default=None),
    status_code: Optional[int] = Query(default=None),
):
    enforce_permission(identity["user"], "logs:read")
    query = select(UsageLog)
    if api_key_id is not None:
        query = query.where(UsageLog.api_key_id == api_key_id)
    if route_id is not None:
        query = query.where(UsageLog.route_id == route_id)
    if status_code is not None:
        query = query.where(UsageLog.status_code == status_code)
    return db.execute(query.order_by(UsageLog.created_at.desc()).limit(200)).scalars().all()


@router.get("/credit-ledger", response_model=list[CreditLedgerRead])
def list_credit_ledger(identity=Depends(admin_identity), db: Session = Depends(get_db), api_key_id: Optional[int] = Query(default=None)):
    enforce_permission(identity["user"], "ledger:read")
    query = select(CreditTransaction)
    if api_key_id is not None:
        query = query.where(CreditTransaction.api_key_id == api_key_id)
    return db.execute(query.order_by(CreditTransaction.created_at.desc()).limit(200)).scalars().all()


@router.get("/audit-log", response_model=list[AuditLogRead])
def list_audit_log(identity=Depends(admin_identity), db: Session = Depends(get_db)):
    enforce_permission(identity["user"], "audit:read")
    return db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)).scalars().all()


@router.post("/jobs/run-renewal")
def run_renewal(identity=Depends(admin_identity), db: Session = Depends(get_db), config_store: ConfigStore = Depends(get_config_store)):
    if identity["user"].role.name != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin required")
    keys = db.execute(select(ApiKey).join(Plan).where(ApiKey.active.is_(True), Plan.active.is_(True))).scalars().all()
    touched = 0
    for key in keys:
        plan = db.get(Plan, key.plan_id)
        previous = key.credit_balance
        key.credit_balance = plan.base_credits
        db.add(CreditTransaction(api_key_id=key.id, delta=plan.base_credits - previous, reason="scheduled_renewal", balance_after=key.credit_balance))
        config_store.set_balance(key.id, key.credit_balance)
        touched += 1
    audit(db, identity["user"].id, "run", "jobs", "renewal", None, {"renewed_keys": touched, "ran_at": datetime.utcnow().isoformat()})
    db.commit()
    return {"renewed_keys": touched}

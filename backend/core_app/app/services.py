from __future__ import annotations

from datetime import datetime, timedelta
from fnmatch import fnmatch
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .models import ApiKey, AuditLog, CreditTransaction, Organization, Plan, Role, RolePermission, Route, UsageLog, User
from .security import generate_api_key, hash_api_key, hash_password, verify_password
from .state import AppState


ROLE_SEEDS: dict[str, list[str]] = {
    "super_admin": ["*"],
    "org_admin": [
        "organizations:read",
        "users:read",
        "users:write",
        "roles:read",
        "plans:read",
        "plans:write",
        "routes:read",
        "routes:write",
        "keys:read",
        "keys:write",
        "logs:read",
        "ledger:read",
        "audit:read",
    ],
    "developer": ["me:read", "usage:read:own", "balance:read:own"],
    "service_owner": ["routes:read", "routes:write", "logs:read"],
    "auditor": ["logs:read", "ledger:read", "audit:read", "plans:read", "routes:read", "keys:read", "roles:read"],
}


def model_to_dict(instance: Any, fields: list[str]) -> dict[str, Any]:
    return {field: getattr(instance, field) for field in fields}


def make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: make_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [make_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


class ConfigStore:
    def __init__(self, app_state: AppState):
        self.app_state = app_state

    def invalidate(self, prefix: str) -> None:
        self.app_state.config_cache.invalidate(prefix)
        self.app_state.balance_cache.invalidate("")
        self.app_state.rate_limits.reset()

    def get_api_key_bundle(self, db: Session, key_id: int) -> tuple[ApiKey, Plan, User]:
        cache_key = f"key:{key_id}"
        cached = self.app_state.config_cache.get(cache_key)
        if cached:
            return cached
        record = db.execute(
            select(ApiKey)
            .where(ApiKey.id == key_id)
            .options(joinedload(ApiKey.plan), joinedload(ApiKey.user).joinedload(User.role).joinedload(Role.permissions))
        ).unique().scalar_one_or_none()
        if not record:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key not found")
        bundle = (record, record.plan, record.user)
        self.app_state.config_cache.set(cache_key, bundle)
        return bundle

    def resolve_token_key(self, db: Session, raw_api_key: str) -> tuple[ApiKey, Plan, User]:
        key_hash = hash_api_key(raw_api_key)
        record = db.execute(
            select(ApiKey)
            .where(ApiKey.key_hash == key_hash)
            .options(joinedload(ApiKey.plan), joinedload(ApiKey.user).joinedload(User.role).joinedload(Role.permissions))
        ).unique().scalar_one_or_none()
        if not record:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        return record, record.plan, record.user

    def resolve_route(self, db: Session, method: str, path: str) -> Route:
        cache_key = f"route:{method}:{path}"
        cached = self.app_state.config_cache.get(cache_key)
        if cached:
            return cached
        routes = db.execute(select(Route).where(Route.active.is_(True), Route.method == method.upper())).scalars().all()
        routes = sorted(routes, key=lambda route: (route.path_pattern.count("*"), -len(route.path_pattern)))
        for route in routes:
            if fnmatch(path, route.path_pattern):
                self.app_state.config_cache.set(cache_key, route)
                return route
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

    def get_balance(self, db: Session, api_key_id: int) -> float:
        cache_key = f"balance:{api_key_id}"
        cached = self.app_state.balance_cache.get(cache_key)
        if cached is not None:
            return cached
        balance = db.get(ApiKey, api_key_id).credit_balance
        self.app_state.balance_cache.set(cache_key, balance)
        return balance

    def set_balance(self, api_key_id: int, balance: float) -> None:
        self.app_state.balance_cache.set(f"balance:{api_key_id}", balance)

    def get_user_bundle(self, db: Session, user_id: int) -> User:
        cache_key = f"user:{user_id}"
        cached = self.app_state.config_cache.get(cache_key)
        if cached:
            return cached
        user = db.execute(
            select(User).where(User.id == user_id).options(joinedload(User.role).joinedload(Role.permissions))
        ).unique().scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        self.app_state.config_cache.set(cache_key, user)
        return user


def ensure_key_active(api_key: ApiKey) -> None:
    now = datetime.utcnow()
    if not api_key.active or api_key.valid_until < now or api_key.valid_from > now:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key is not currently valid")


def ensure_key_exchangeable(api_key: ApiKey) -> None:
    now = datetime.utcnow()
    if not api_key.active or api_key.valid_until < now:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key is not currently valid")


def ensure_admin_login_allowed(user: User) -> None:
    if not user.password_hash:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin password login is not enabled for this user")


def get_permissions(user: User) -> set[str]:
    return {perm.permission for perm in user.role.permissions}


def has_permission(user: User, permission: str) -> bool:
    permissions = get_permissions(user)
    return "*" in permissions or permission in permissions


def enforce_permission(user: User, permission: str) -> None:
    if not has_permission(user, permission):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


def enforce_org_scope(user: User, org_id: int | None) -> None:
    if has_permission(user, "*"):
        return
    if user.role.name == "org_admin" and org_id is not None and org_id != user.org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-organization access denied")
    if user.role.name not in {"org_admin", "super_admin"} and org_id is not None and org_id != user.org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-organization access denied")


def audit(db: Session, actor_user_id: int | None, action: str, target_table: str, target_id: str, before: dict | None, after: dict | None) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            target_table=target_table,
            target_id=target_id,
            before=make_json_safe(before),
            after=make_json_safe(after),
        )
    )


def create_api_key_record(db: Session, user_id: int, plan: Plan, valid_from: datetime | None, valid_until: datetime | None, active: bool) -> tuple[str, ApiKey]:
    raw = generate_api_key()
    start = valid_from or datetime.utcnow()
    end = valid_until or (start + timedelta(days=plan.valid_days))
    record = ApiKey(
        key_hash=hash_api_key(raw),
        user_id=user_id,
        plan_id=plan.id,
        credit_balance=plan.base_credits,
        valid_from=start,
        valid_until=end,
        active=active,
    )
    db.add(record)
    db.flush()
    return raw, record


def apply_credit_change(db: Session, config_store: ConfigStore, api_key: ApiKey, delta: float, reason: str) -> CreditTransaction:
    api_key.credit_balance = round(api_key.credit_balance + delta, 4)
    txn = CreditTransaction(api_key_id=api_key.id, delta=delta, reason=reason, balance_after=api_key.credit_balance)
    db.add(txn)
    db.flush()
    config_store.set_balance(api_key.id, api_key.credit_balance)
    return txn


def authenticate_admin_login(db: Session, email: str, password: str) -> User:
    user = db.execute(
        select(User).where(User.email == email).options(joinedload(User.role).joinedload(Role.permissions))
    ).unique().scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials")
    ensure_admin_login_allowed(user)
    return user


def ensure_demo_admin(db: Session, demo_admin_email: str, demo_admin_password: str) -> User | None:
    super_admin_role = db.execute(select(Role).where(Role.name == "super_admin")).scalar_one_or_none()
    if not super_admin_role:
        return None

    demo_org = db.execute(select(Organization).where(Organization.name == "Demo Org")).scalar_one_or_none()
    if not demo_org:
        demo_org = Organization(name="Demo Org")
        db.add(demo_org)
        db.flush()

    desired_password_hash = hash_password(demo_admin_password)
    user = db.execute(select(User).where(User.email == demo_admin_email)).scalar_one_or_none()

    if not user:
        user = (
            db.execute(
                select(User).join(Role).where(Role.name == "super_admin").order_by(User.id.asc())
            )
            .scalars()
            .first()
        )

    if user:
        user.email = demo_admin_email
        user.password_hash = desired_password_hash
        user.role_id = super_admin_role.id
        user.org_id = demo_org.id
    else:
        user = User(
            email=demo_admin_email,
            password_hash=desired_password_hash,
            role_id=super_admin_role.id,
            org_id=demo_org.id,
        )
        db.add(user)
        db.flush()

    return user


def log_usage(db: Session, api_key_id: int, route_id: int, status_code: int, latency_ms: float, credits_charged: float) -> None:
    db.add(
        UsageLog(
            api_key_id=api_key_id,
            route_id=route_id,
            status_code=status_code,
            latency_ms=latency_ms,
            credits_charged=credits_charged,
        )
    )


def seed_defaults(db: Session, upstream_url: str, demo_admin_email: str, demo_admin_password: str) -> dict[str, str]:
    if db.execute(select(Role)).first():
        return {}
    org = Organization(name="Demo Org")
    alt_org = Organization(name="Partner Org")
    db.add_all([org, alt_org])
    db.flush()
    roles = {}
    for name, permissions in ROLE_SEEDS.items():
        role = Role(name=name)
        db.add(role)
        db.flush()
        for permission in permissions:
            db.add(RolePermission(role_id=role.id, permission=permission))
        roles[name] = role
    plans = [
        Plan(name="Free", org_id=None, rate_limit=3, rate_window_secs=60, credit_cost_multiplier=1.0, renewal_frequency="daily", base_credits=10, valid_days=30, active=True),
        Plan(name="Basic", org_id=None, rate_limit=10, rate_window_secs=60, credit_cost_multiplier=1.0, renewal_frequency="weekly", base_credits=50, valid_days=60, active=True),
        Plan(name="Pro", org_id=None, rate_limit=30, rate_window_secs=60, credit_cost_multiplier=0.75, renewal_frequency="monthly", base_credits=200, valid_days=90, active=True),
    ]
    db.add_all(plans)
    db.flush()
    db.add_all(
        [
            Route(path_pattern="/api/catalog/products", method="GET", category="public", base_credit_cost=1, base_rate_limit=5, base_rate_window_secs=60, upstream_url=f"{upstream_url}/public/products", active=True),
            Route(path_pattern="/api/catalog/products/*", method="GET", category="public", base_credit_cost=1, base_rate_limit=5, base_rate_window_secs=60, upstream_url=f"{upstream_url}/public/products", active=True),
            Route(path_pattern="/api/inventory/*", method="GET", category="standard", base_credit_cost=2, base_rate_limit=4, base_rate_window_secs=60, upstream_url=f"{upstream_url}/standard/inventory", active=True),
            Route(path_pattern="/api/reviews/*", method="GET", category="standard", base_credit_cost=2, base_rate_limit=4, base_rate_window_secs=60, upstream_url=f"{upstream_url}/standard/reviews", active=True),
            Route(path_pattern="/api/recommendations", method="POST", category="premium", base_credit_cost=4, base_rate_limit=2, base_rate_window_secs=60, upstream_url=f"{upstream_url}/premium/recommendations", active=True),
            Route(path_pattern="/api/analytics/customer-segment/*", method="GET", category="premium", base_credit_cost=4, base_rate_limit=2, base_rate_window_secs=60, upstream_url=f"{upstream_url}/premium/analytics/customer-segment", active=True),
            Route(path_pattern="/api/analytics/fail", method="GET", category="premium", base_credit_cost=4, base_rate_limit=2, base_rate_window_secs=60, upstream_url=f"{upstream_url}/premium/analytics/fail", active=True),
        ]
    )
    db.flush()
    raw_keys: dict[str, str] = {}
    for role_name, role in roles.items():
        email = demo_admin_email if role_name == "super_admin" else f"{role_name}@demo.local"
        password_hash = hash_password(demo_admin_password) if role_name == "super_admin" else None
        user = User(
            email=email,
            password_hash=password_hash,
            role_id=role.id,
            org_id=org.id if role_name != "service_owner" else alt_org.id,
        )
        db.add(user)
        db.flush()
        if role_name in {"super_admin", "org_admin"}:
            plan = plans[2]
        elif role_name == "developer":
            plan = plans[0]
        else:
            plan = plans[1]
        raw, record = create_api_key_record(db, user.id, plan, None, None, True)
        raw_keys[role_name] = raw
        db.add(record)
    db.commit()
    return raw_keys

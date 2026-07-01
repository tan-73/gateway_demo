from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .dependencies import get_config_store
from .schemas import AdminLoginRequest, BootstrapStatusResponse, TokenRequest, TokenResponse
from .security import create_access_token
from .services import ConfigStore, authenticate_admin_login, ensure_key_exchangeable

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
def create_token(payload: TokenRequest, db: Session = Depends(get_db), config_store: ConfigStore = Depends(get_config_store)):
    api_key, plan, user = config_store.resolve_token_key(db, payload.api_key)
    ensure_key_exchangeable(api_key)
    token, expires_in = create_access_token(
        {
            "user_id": user.id,
            "org_id": user.org_id,
            "role": user.role.name,
            "plan_id": plan.id,
            "key_id": api_key.id,
        }
    )
    return TokenResponse(access_token=token, expires_in=expires_in, role=user.role.name)


@router.post("/admin-login", response_model=TokenResponse)
def admin_login(payload: AdminLoginRequest, db: Session = Depends(get_db)):
    user = authenticate_admin_login(db, payload.email, payload.password)
    token, expires_in = create_access_token(
        {
            "user_id": user.id,
            "org_id": user.org_id,
            "role": user.role.name,
            "auth_mode": "admin_login",
        }
    )
    return TokenResponse(access_token=token, expires_in=expires_in, role=user.role.name)


@router.get("/bootstrap-status", response_model=BootstrapStatusResponse)
def bootstrap_status():
    settings = get_settings()
    return BootstrapStatusResponse(
        admin_email=settings.demo_admin_email,
        admin_password_configured=bool(settings.demo_admin_password),
        seeded_keys_available=False,
    )

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from .database import get_db
from .security import decode_access_token
from .services import ConfigStore, ensure_key_active


DBSession = Annotated[Session, Depends(get_db)]


def get_config_store(request: Request) -> ConfigStore:
    return request.app.state.config_store


def get_current_identity(
    request: Request,
    db: DBSession,
    config_store: Annotated[ConfigStore, Depends(get_config_store)],
    authorization: Annotated[Optional[str], Header()] = None,
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        claims = decode_access_token(token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    if claims.get("auth_mode") == "admin_login":
        user = config_store.get_user_bundle(db, claims["user_id"])
        return {"claims": claims, "api_key": None, "plan": None, "user": user}
    api_key, plan, user = config_store.get_api_key_bundle(db, claims["key_id"])
    ensure_key_active(api_key)
    return {"claims": claims, "api_key": api_key, "plan": plan, "user": user}


def get_current_consumer_identity(identity=Depends(get_current_identity)):
    if not identity["api_key"] or not identity["plan"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Consumer API key session required")
    return identity

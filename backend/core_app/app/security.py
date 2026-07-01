from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

import jwt

from .config import get_settings


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def hash_password(raw_password: str) -> str:
    return hashlib.sha256(f"gateway-demo::{raw_password}".encode("utf-8")).hexdigest()


def verify_password(raw_password: str, password_hash: str | None) -> bool:
    return bool(password_hash) and hash_password(raw_password) == password_hash


def generate_api_key() -> str:
    return "agw_" + secrets.token_urlsafe(24)


def create_access_token(payload: dict) -> tuple[str, int]:
    settings = get_settings()
    expires = datetime.utcnow() + timedelta(minutes=settings.jwt_expiry_minutes)
    token = jwt.encode({**payload, "exp": expires}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, settings.jwt_expiry_minutes * 60


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

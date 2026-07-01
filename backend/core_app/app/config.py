from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "API Gateway Demo"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 20
    demo_admin_email: str = "admin@gateway-demo.local"
    demo_admin_password: str = "demo-admin-pass"
    sqlite_path: str = str(Path(__file__).resolve().parents[2] / "data" / "gateway_demo.db")
    config_ttl_seconds: int = 5
    balance_ttl_seconds: int = 5
    scheduler_timezone: str = "UTC"
    public_upstream_url: str = "http://127.0.0.1:8101"
    standard_upstream_url: str = "http://127.0.0.1:8102"
    premium_upstream_url: str = "http://127.0.0.1:8103"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    model_config = SettingsConfigDict(env_prefix="GATEWAY_", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    return settings

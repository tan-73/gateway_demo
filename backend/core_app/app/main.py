from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import Base, SessionLocal, engine
from .routers_admin import router as admin_router
from .routers_auth import router as auth_router
from .routers_gateway import router as gateway_router
from .routers_me import router as me_router
from .services import ConfigStore, ensure_demo_admin, seed_defaults
from .state import AppState


def run_scheduled_renewal():
    db = SessionLocal()
    try:
        from sqlalchemy import select

        from .models import ApiKey, CreditTransaction, Plan

        keys = db.execute(select(ApiKey).join(Plan).where(ApiKey.active.is_(True), Plan.active.is_(True))).scalars().all()
        for key in keys:
            plan = db.get(Plan, key.plan_id)
            previous = key.credit_balance
            key.credit_balance = plan.base_credits
            db.add(CreditTransaction(api_key_id=key.id, delta=plan.base_credits - previous, reason="scheduled_renewal", balance_after=key.credit_balance))
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    settings = get_settings()
    raw_keys = seed_defaults(
        db,
        settings.public_upstream_url,
        settings.standard_upstream_url,
        settings.premium_upstream_url,
        settings.demo_admin_email,
        settings.demo_admin_password,
    )
    if raw_keys:
        app.state.seed_keys = raw_keys
    ensure_demo_admin(db, settings.demo_admin_email, settings.demo_admin_password)
    db.commit()
    db.close()
    scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)
    scheduler.add_job(run_scheduled_renewal, "interval", hours=24, id="credit-renewal", replace_existing=True)
    scheduler.start()
    app.state.scheduler = scheduler
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    runtime_state = AppState(settings.config_ttl_seconds, settings.balance_ttl_seconds)
    app.state.runtime_state = runtime_state
    app.state.config_store = ConfigStore(runtime_state)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/seed-keys")
    def seed_keys():
        return getattr(app.state, "seed_keys", {})

    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(me_router)
    app.include_router(gateway_router)

    return app


app = create_app()

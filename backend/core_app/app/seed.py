from .config import get_settings
from .database import Base, SessionLocal, engine
from .services import seed_defaults


def main() -> None:
    Base.metadata.create_all(bind=engine)
    settings = get_settings()
    db = SessionLocal()
    try:
        raw_keys = seed_defaults(
            db,
            settings.public_upstream_url,
            settings.standard_upstream_url,
            settings.premium_upstream_url,
            settings.demo_admin_email,
            settings.demo_admin_password,
        )
        if raw_keys:
            print("Seeded demo API keys:")
            for role, key in raw_keys.items():
                print(f"{role}: {key}")
        else:
            print("Seed data already present.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

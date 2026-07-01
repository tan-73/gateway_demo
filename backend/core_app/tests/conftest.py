import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend" / "core_app"))
sys.path.insert(0, str(ROOT / "backend"))
TEST_DB_DIR = Path(tempfile.gettempdir()) / "gateway_demo_tests"
TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
os.environ["GATEWAY_SQLITE_PATH"] = str(TEST_DB_DIR / "test.db")

from app.config import get_settings
from app.database import Base, engine
from app.main import create_app
from mock_upstream.app.main import app as mock_upstream_app


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app = create_app()
    app.state.runtime_state.upstream_apps = {
        "127.0.0.1:8101": mock_upstream_app,
    }
    with TestClient(app) as test_client:
        yield test_client


def get_token(client: TestClient, api_key: str) -> str:
    response = client.post("/auth/token", json={"api_key": api_key})
    assert response.status_code == 200
    return response.json()["access_token"]


def get_admin_token(client: TestClient, email: str = "admin@gateway-demo.local", password: str = "demo-admin-pass") -> str:
    response = client.post("/auth/admin-login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]

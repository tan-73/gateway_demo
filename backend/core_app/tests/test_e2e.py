from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from .conftest import get_admin_token, get_token


def test_auth_valid_and_invalid(client: TestClient):
    seed = client.get("/seed-keys").json()
    assert client.post("/auth/token", json={"api_key": seed["developer"]}).status_code == 200
    assert client.post("/auth/token", json={"api_key": "bad-key"}).status_code == 401
    assert client.post("/auth/admin-login", json={"email": "admin@gateway-demo.local", "password": "demo-admin-pass"}).status_code == 200


def test_rate_limiting_headers(client: TestClient):
    seed = client.get("/seed-keys").json()
    token = get_token(client, seed["developer"])
    for _ in range(3):
        response = client.get("/api/catalog/products", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert "RateLimit-Limit" in response.headers
        assert "items" in response.json()
    blocked = client.get("/api/catalog/products", headers={"Authorization": f"Bearer {token}"})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_credit_exhaustion_and_upstream_failure_no_charge(client: TestClient):
    seed = client.get("/seed-keys").json()
    token = get_token(client, seed["developer"])
    admin_token = get_admin_token(client)
    keys = client.get("/admin/api-keys", headers={"Authorization": f"Bearer {admin_token}"}).json()
    developer_key = next(key for key in keys if key["user_id"] == 3)
    client.patch(
        f"/admin/api-keys/{developer_key['id']}",
        json={"credit_balance": 4},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    success = client.post(
        "/api/recommendations",
        json={"customer_id": "cust-1", "cart": ["sku-1"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert success.status_code == 200
    assert "suggestions" in success.json()
    balance = client.get("/me/credit-balance", headers={"Authorization": f"Bearer {token}"}).json()
    assert balance["credit_balance"] == 0.0
    client.patch(
        f"/admin/api-keys/{developer_key['id']}",
        json={"credit_balance": 4},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    fail = client.get("/api/analytics/fail", headers={"Authorization": f"Bearer {token}"})
    assert fail.status_code == 500
    after_fail = client.get("/me/credit-balance", headers={"Authorization": f"Bearer {token}"}).json()
    assert after_fail["credit_balance"] == 4.0


def test_time_limits(client: TestClient):
    admin_token = get_admin_token(client)
    users = client.get("/admin/users", headers={"Authorization": f"Bearer {admin_token}"}).json()
    plans = client.get("/admin/plans", headers={"Authorization": f"Bearer {admin_token}"}).json()
    developer = next(user for user in users if user["email"] == "developer@demo.local")
    plan = plans[0]
    response = client.post(
        "/admin/api-keys",
        json={
            "user_id": developer["id"],
            "plan_id": plan["id"],
            "valid_from": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "valid_until": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    raw_key = response.json()["api_key"]
    token = client.post("/auth/token", json={"api_key": raw_key}).json()["access_token"]
    forbidden = client.get("/api/catalog/products", headers={"Authorization": f"Bearer {token}"})
    assert forbidden.status_code == 403


def test_dynamic_config_change(client: TestClient):
    seed = client.get("/seed-keys").json()
    admin_token = get_admin_token(client)
    token = get_token(client, seed["developer"])
    route = next(item for item in client.get("/admin/routes", headers={"Authorization": f"Bearer {admin_token}"}).json() if item["path_pattern"] == "/api/catalog/products")
    for _ in range(3):
        assert client.get("/api/catalog/products", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    client.patch(
        f"/admin/routes/{route['id']}",
        json={"base_rate_limit": 10},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    follow_up = client.get("/api/catalog/products", headers={"Authorization": f"Bearer {token}"})
    assert follow_up.status_code == 200


def test_manual_renewal_writes_ledger(client: TestClient):
    seed = client.get("/seed-keys").json()
    admin_token = get_admin_token(client)
    token = get_token(client, seed["developer"])
    client.get("/api/catalog/products", headers={"Authorization": f"Bearer {token}"})
    result = client.post("/admin/jobs/run-renewal", headers={"Authorization": f"Bearer {admin_token}"})
    assert result.status_code == 200
    ledger = client.get("/admin/credit-ledger", headers={"Authorization": f"Bearer {admin_token}"}).json()
    assert any(item["reason"] == "scheduled_renewal" for item in ledger)


def test_rbac_enforcement(client: TestClient):
    seed = client.get("/seed-keys").json()
    auditor = get_token(client, seed["auditor"])
    developer = get_token(client, seed["developer"])
    org_admin = get_token(client, seed["org_admin"])
    assert client.post("/admin/jobs/run-renewal", headers={"Authorization": f"Bearer {auditor}"}).status_code == 403
    assert client.get("/admin/plans", headers={"Authorization": f"Bearer {developer}"}).status_code == 403
    assert client.post("/admin/organizations", json={"name": "Cross Org"}, headers={"Authorization": f"Bearer {org_admin}"}).status_code == 403


def test_full_happy_path(client: TestClient):
    seed = client.get("/seed-keys").json()
    admin_token = get_admin_token(client)
    org = client.post("/admin/organizations", json={"name": "Acme"}, headers={"Authorization": f"Bearer {admin_token}"}).json()
    role = next(item for item in client.get("/admin/roles", headers={"Authorization": f"Bearer {admin_token}"}).json() if item["name"] == "developer")
    user = client.post(
        "/admin/users",
        json={"email": "newdev@acme.local", "role_id": role["id"], "org_id": org["id"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    plan = client.post(
        "/admin/plans",
        json={
            "name": "Acme Plan",
            "org_id": org["id"],
            "rate_limit": 5,
            "rate_window_secs": 60,
            "credit_cost_multiplier": 1.0,
            "renewal_frequency": "daily",
            "base_credits": 20,
            "valid_days": 30,
            "active": True,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    route = client.post(
        "/admin/routes",
        json={
            "path_pattern": "/api/acme/featured-products",
            "method": "GET",
            "category": "public",
            "base_credit_cost": 1,
            "base_rate_limit": 5,
            "base_rate_window_secs": 60,
            "upstream_url": "http://127.0.0.1:8101/public/products",
            "active": True,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    key = client.post(
        "/admin/api-keys",
        json={"user_id": user["id"], "plan_id": plan["id"], "active": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    token = get_token(client, key["api_key"])
    response = client.get("/api/acme/featured-products", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert "items" in response.json()
    ledger = client.get("/admin/credit-ledger", headers={"Authorization": f"Bearer {admin_token}"}).json()
    logs = client.get("/admin/usage-logs", headers={"Authorization": f"Bearer {admin_token}"}).json()
    assert any(item["api_key_id"] == key["record"]["id"] for item in ledger)
    assert any(item["route_id"] == route["id"] for item in logs)

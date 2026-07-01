import time
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .database import get_db
from .dependencies import get_config_store, get_current_consumer_identity
from .models import ApiKey, Plan, Route
from .services import ConfigStore, apply_credit_change, log_usage

router = APIRouter(tags=["gateway"])


def build_upstream_url(route: Route, path: str, query: str) -> str:
    upstream_url = route.upstream_url.rstrip("/")
    if "*" in route.path_pattern:
        prefix = route.path_pattern.split("*", 1)[0]
        suffix = path[len(prefix):].lstrip("/")
        if suffix:
            upstream_url = f"{upstream_url}/{suffix}"
    if query:
        return f"{upstream_url}?{query}"
    return upstream_url


async def proxy_request(request: Request, upstream_url: str) -> Response:
    upstream_apps = request.app.state.runtime_state.upstream_apps
    parsed = urlparse(upstream_url)
    transport = None
    if parsed.netloc in upstream_apps:
        transport = httpx.ASGITransport(app=upstream_apps[parsed.netloc])
    forward_headers = {k: v for k, v in request.headers.items() if k.lower() not in {"host", "accept-encoding"}}
    forward_headers["accept-encoding"] = "identity"
    async with httpx.AsyncClient(transport=transport, timeout=10.0) as client:
        response = await client.request(
            method=request.method,
            url=upstream_url,
            headers=forward_headers,
            content=await request.body(),
        )
    return Response(content=response.content, status_code=response.status_code, media_type=response.headers.get("content-type"))


def effective_limit(plan: Plan, route: Route) -> tuple[int, int]:
    limit = min(plan.rate_limit, route.base_rate_limit)
    window = min(plan.rate_window_secs, route.base_rate_window_secs)
    return limit, window


@router.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def gateway(
    full_path: str,
    request: Request,
    identity=Depends(get_current_consumer_identity),
    db: Session = Depends(get_db),
    config_store: ConfigStore = Depends(get_config_store),
):
    path = "/" + full_path
    route = config_store.resolve_route(db, request.method, path)
    plan = identity["plan"]
    api_key: ApiKey = identity["api_key"]
    limit, window = effective_limit(plan, route)
    result = await request.app.state.runtime_state.rate_limits.check(f"{api_key.id}:{route.id}", limit, window)
    headers = {
        "RateLimit-Limit": str(result.limit),
        "RateLimit-Remaining": str(result.remaining),
        "RateLimit-Reset": str(result.reset_after),
    }
    if not result.allowed:
        headers["Retry-After"] = str(result.retry_after)
        raise HTTPException(status_code=429, detail="Rate limit exceeded", headers=headers)
    cost = round(route.base_credit_cost * plan.credit_cost_multiplier, 4)
    current_balance = config_store.get_balance(db, api_key.id)
    if current_balance < cost:
        raise HTTPException(status_code=402, detail="Insufficient credits", headers=headers)
    start = time.perf_counter()
    response = await proxy_request(request, build_upstream_url(route, path, request.url.query))
    latency_ms = (time.perf_counter() - start) * 1000
    charged = 0.0
    if response.status_code < 500:
        refreshed = db.get(ApiKey, api_key.id)
        apply_credit_change(db, config_store, refreshed, -cost, "request_charge")
        charged = cost
    log_usage(db, api_key.id, route.id, response.status_code, latency_ms, charged)
    db.commit()
    for key, value in headers.items():
        response.headers[key] = value
    return response

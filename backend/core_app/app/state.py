from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds
        self._values: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._values.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at < time.time():
            self._values.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._values[key] = (time.time() + self.ttl_seconds, value)

    def invalidate(self, prefix: str) -> None:
        for key in list(self._values):
            if key.startswith(prefix):
                self._values.pop(key, None)


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_after: int
    retry_after: int


class RateLimitStore:
    def __init__(self):
        self._locks: dict[str, asyncio.Lock] = {}
        self._state: dict[str, tuple[float, float]] = {}

    async def check(self, key: str, capacity: int, window_secs: int) -> RateLimitResult:
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            refill_rate = capacity / window_secs
            tokens, updated_at = self._state.get(key, (float(capacity), now))
            tokens = min(float(capacity), tokens + (now - updated_at) * refill_rate)
            allowed = tokens >= 1.0
            if allowed:
                tokens -= 1.0
            self._state[key] = (tokens, now)
            remaining = max(0, math.floor(tokens))
            missing = max(0.0, 1.0 - tokens)
            retry_after = 0 if allowed else max(1, math.ceil(missing / refill_rate))
            reset_after = max(1, math.ceil((capacity - tokens) / refill_rate)) if tokens < capacity else window_secs
            return RateLimitResult(allowed, capacity, remaining, reset_after, retry_after)

    def reset(self) -> None:
        self._state.clear()


class AppState:
    def __init__(self, config_ttl: int, balance_ttl: int):
        self.config_cache = TTLCache(config_ttl)
        self.balance_cache = TTLCache(balance_ttl)
        self.rate_limits = RateLimitStore()
        self.upstream_apps: dict[str, Any] = {}

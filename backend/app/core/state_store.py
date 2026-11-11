"""
Parakh — shared state store.

Redis when REDIS_URL is reachable, in-process memory otherwise. Every caller
goes through this module so rate limits, the kill switch and short-lived
caches survive restarts and work across several uvicorn workers once Redis
is configured. In memory mode the behaviour is identical for one process.
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, Optional, Tuple

_lock = threading.Lock()
_mem: Dict[str, Tuple[float, str]] = {}          # key -> (expires_at, value)
_buckets: Dict[str, Deque[float]] = {}
_redis = None
_redis_checked = False
_PREFIX = "parakh:"


def _client():
    """Lazily connect to Redis once; fall back to memory on any failure."""
    global _redis, _redis_checked
    if _redis_checked:
        return _redis
    _redis_checked = True
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        return None
    try:
        import redis  # type: ignore
        client = redis.Redis.from_url(url, socket_connect_timeout=0.5,
                                      socket_timeout=0.5, decode_responses=True)
        client.ping()
        _redis = client
    except Exception:
        _redis = None
    return _redis


def backend() -> str:
    return "redis" if _client() is not None else "memory"


def reset_for_tests() -> None:
    global _redis, _redis_checked
    with _lock:
        _mem.clear()
        _buckets.clear()
    _redis, _redis_checked = None, False


def set_json(key: str, value: Any, ttl_s: Optional[int] = None) -> None:
    raw = json.dumps(value, default=str)
    r = _client()
    if r is not None:
        try:
            r.set(_PREFIX + key, raw, ex=ttl_s)
            return
        except Exception:
            pass
    with _lock:
        _mem[key] = (time.time() + ttl_s if ttl_s else float("inf"), raw)


def get_json(key: str, default: Any = None) -> Any:
    r = _client()
    if r is not None:
        try:
            raw = r.get(_PREFIX + key)
            return json.loads(raw) if raw is not None else default
        except Exception:
            pass
    with _lock:
        hit = _mem.get(key)
        if not hit:
            return default
        exp, raw = hit
        if exp < time.time():
            _mem.pop(key, None)
            return default
    return json.loads(raw)


def delete(key: str) -> None:
    r = _client()
    if r is not None:
        try:
            r.delete(_PREFIX + key)
        except Exception:
            pass
    with _lock:
        _mem.pop(key, None)


def rate_hit(key: str, window_s: int, max_hits: int) -> bool:
    """Record one hit. Returns True when the caller is still within budget."""
    r = _client()
    if r is not None:
        try:
            k = f"{_PREFIX}rl:{key}:{int(time.time() // window_s)}"
            pipe = r.pipeline()
            pipe.incr(k)
            pipe.expire(k, window_s + 1)
            count, _ = pipe.execute()
            return int(count) <= max_hits
        except Exception:
            pass
    now = time.monotonic()
    with _lock:
        bucket = _buckets.setdefault(key, deque())
        cutoff = now - window_s
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= max_hits:
            return False
        bucket.append(now)
        return True

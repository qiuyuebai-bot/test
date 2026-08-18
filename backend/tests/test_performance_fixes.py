"""Regression tests for the shared-cache and readiness performance fixes."""

import json
import time
from types import SimpleNamespace

from starlette.requests import Request

from app import health
from app.domains.knowledge import service as knowledge_service
from app.utils.llm import LLMUtil
from app.utils.rate_limiter import SlidingWindowRateLimiter


class _FakeRedis:
    def __init__(self):
        self.values = {}
        self.eval_result = [1, 0]
        self.eval_calls = []
        self.set_calls = []

    def eval(self, *args):
        self.eval_calls.append(args)
        return self.eval_result

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex):
        self.set_calls.append((key, value, ex))
        self.values[key] = value


def test_rate_limiter_uses_atomic_redis_result():
    redis = _FakeRedis()
    limiter = SlidingWindowRateLimiter(redis_url="redis://test")
    limiter._get_redis_client = lambda: redis

    assert limiter.is_allowed("ip:/api", 10, 60) == (True, 0)
    assert redis.eval_calls
    assert redis.eval_calls[0][1] == 1
    assert redis.eval_calls[0][2] == "rate-limit:ip:/api"

    redis.eval_result = [0, 7]
    assert limiter.is_allowed("ip:/api", 10, 60) == (False, 7)


def test_llm_cache_round_trips_through_redis(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr(
        LLMUtil,
        "_get_redis_cache_client",
        classmethod(lambda cls: redis),
    )
    LLMUtil._response_cache.clear()
    LLMUtil._cache_hits = 0
    LLMUtil._cache_misses = 0

    value = ("cached answer", {"total_tokens": 3})
    LLMUtil._set_cached_response("cache-key", value, ttl=60)
    LLMUtil._response_cache.clear()

    assert LLMUtil._get_cached_response("cache-key") == value
    assert redis.set_calls[0][0] == "llm:response:v1:cache-key"
    assert json.loads(redis.set_calls[0][1])["value"] == "cached answer"


def test_readiness_success_is_cached(monkeypatch, db_session):
    health._readiness_cache = None
    calls = {"sessions": 0}

    def session_factory():
        calls["sessions"] += 1
        return db_session

    monkeypatch.setattr(health, "SessionLocal", session_factory)
    monkeypatch.setattr(knowledge_service, "_get_chroma_collection", lambda: None)
    app = SimpleNamespace(state=SimpleNamespace(start_time=time.time()))
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/health/ready",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "app": app,
        }
    )

    first = health.health_readiness(request)
    second = health.health_readiness(request)

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls["sessions"] == 1

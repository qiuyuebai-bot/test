"""LLM httpx 客户端单例并发创建回归测试（check-then-act 竞态修复）。"""
import threading

import app.utils.llm as llm_module
from app.utils.llm import LLMUtil


def _run_concurrent_getter(getter, workers=16):
    """barrier 对齐后并发调用 getter，返回 clients。"""
    barrier = threading.Barrier(workers)
    clients = []

    def worker():
        barrier.wait()
        clients.append(getter())

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    return clients


def test_sync_client_created_once_under_concurrency(monkeypatch):
    created = []

    class CountingClient(llm_module.httpx.Client):
        def __init__(self, *args, **kwargs):
            created.append(1)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(llm_module.httpx, "Client", CountingClient)

    LLMUtil._sync_client = None
    try:
        clients = _run_concurrent_getter(LLMUtil._get_sync_client)
        assert len(clients) == 16
        assert all(c is clients[0] for c in clients)
        assert len(created) == 1  # 旧代码：多线程同时通过 None 检查 → created > 1
    finally:
        LLMUtil.close_clients()
        LLMUtil._sync_client = None


def test_async_client_created_once_under_concurrency(monkeypatch):
    created = []

    class CountingAsyncClient(llm_module.httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            created.append(1)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(llm_module.httpx, "AsyncClient", CountingAsyncClient)

    LLMUtil._async_client = None
    try:
        clients = _run_concurrent_getter(LLMUtil._get_async_client)
        assert len(clients) == 16
        assert all(c is clients[0] for c in clients)
        assert len(created) == 1
    finally:
        LLMUtil._async_client = None

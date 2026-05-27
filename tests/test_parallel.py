from __future__ import annotations

import threading
import time

import pytest

import tinydata.parallel as parallel_module
from tinydata.errors import TinyDataParameterError, TinyDataRateLimitError
from tinydata.parallel import run_parallel_code_queries


def test_run_parallel_code_queries_reduce_wall_time():
    barrier = threading.Barrier(2)

    def fetch_one(code: str) -> str:
        try:
            barrier.wait(timeout=0.3)
        except threading.BrokenBarrierError:
            pass
        time.sleep(0.05)
        return code

    started = time.perf_counter()
    out = run_parallel_code_queries(
        ["A", "B"],
        fetch_one=fetch_one,
        max_workers=2,
        description="parallel test",
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 0.3
    assert out == ["A", "B"]


def test_run_parallel_code_queries_updates_progress(monkeypatch):
    captured = {"updates": []}

    class FakeProgress:
        def __init__(self, *, enabled, total, description):
            captured["enabled"] = enabled
            captured["total"] = total
            captured["description"] = description

        def __enter__(self):
            captured["entered"] = True
            return self

        def __exit__(self, exc_type, exc, tb):
            captured["closed"] = True
            return False

        def update(self, step=1):
            captured["updates"].append(step)

    def fake_create_progress_tracker(*, enabled, total, description):
        return FakeProgress(enabled=enabled, total=total, description=description)

    monkeypatch.setattr(parallel_module, "_create_progress_tracker", fake_create_progress_tracker)

    out = run_parallel_code_queries(
        ["A", "B"],
        fetch_one=lambda code: code,
        max_workers=2,
        progress=True,
        description="parallel progress",
    )

    assert captured["enabled"] is True
    assert captured["total"] == 2
    assert captured["description"] == "parallel progress"
    assert captured["updates"] == [1, 1]
    assert captured["entered"] is True
    assert captured["closed"] is True
    assert out == ["A", "B"]


def test_run_parallel_code_queries_reduce_workers_after_rate_limit(caplog):
    state = {"active": 0, "max_active": 0}
    lock = threading.Lock()

    def fetch_one(code: str) -> str:
        with lock:
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
            current = state["active"]
        time.sleep(0.02)
        with lock:
            state["active"] -= 1
        if current > 1:
            raise TinyDataRateLimitError("HTTP 429")
        return code

    out = run_parallel_code_queries(
        ["A", "B"],
        fetch_one=fetch_one,
        max_workers=2,
        description="parallel retry",
    )

    assert state["max_active"] >= 2
    assert "retrying 1 failed code request(s) with max_workers=1" in caplog.text.lower()
    assert out == ["A", "B"]


def test_run_parallel_code_queries_reject_invalid_max_workers():
    with pytest.raises(TinyDataParameterError, match="max_workers"):
        run_parallel_code_queries(
            ["A"],
            fetch_one=lambda code: code,
            max_workers=0,
            description="invalid workers",
        )
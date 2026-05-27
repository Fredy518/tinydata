from __future__ import annotations

import threading
import time

import pandas as pd
import pytest

from tinydata.errors import TinyDataParameterError, TinyDataQueryError, TinyDataRateLimitError
from tinydata.infotable import InfoTableOptions, build_where_clause, parse_tinysoft_date, query_infotable


class FakeClient:
    def __init__(self):
        self.queries = []

    def exec(self, tsl_code, *, as_dataframe=True, timeout_ms=None):
        self.queries.append(tsl_code)
        if "infotable 999" in tsl_code:
            raise TinyDataQueryError("select 查询的股票为空")
        if "array(" in tsl_code:
            return pd.DataFrame({"value": [1]})
        if "'SZ000001'" in tsl_code:
            return pd.DataFrame({"StockID": ["SZ000001"], "value": [10]})
        if "'SH600000'" in tsl_code:
            return pd.DataFrame({"StockID": ["SH600000"], "value": [20]})
        return pd.DataFrame({"StockID": ["SZ000001"], "value": [1]})


def test_query_infotable_batch_falls_back_when_identifier_missing():
    client = FakeClient()
    df = query_infotable(
        client,
        10,
        codes=["000001.SZ", "600000.SH"],
        options=InfoTableOptions(code_batch_size=100, retries=1),
    )
    assert list(df["StockID"]) == ["SZ000001", "SH600000"]
    assert any("array(" in q for q in client.queries)
    assert any("'SZ000001'" in q for q in client.queries)


def test_query_infotable_full_table_stock_empty_message():
    client = FakeClient()
    with pytest.raises(TinyDataQueryError, match="requires codes"):
        query_infotable(client, 999, allow_full_table=True, options=InfoTableOptions(retries=1))


def test_query_infotable_parallel_batches_reduce_wall_time():
    class SlowClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.barrier = threading.Barrier(2)

        def exec(self, tsl_code, *, as_dataframe=True, timeout_ms=None):
            try:
                self.barrier.wait(timeout=0.3)
            except threading.BrokenBarrierError:
                pass
            time.sleep(0.05)
            return super().exec(tsl_code, as_dataframe=as_dataframe, timeout_ms=timeout_ms)

    client = SlowClient()
    started = time.perf_counter()
    out = query_infotable(
        client,
        10,
        codes=["000001.SZ", "600000.SH"],
        options=InfoTableOptions(code_batch_size=1, retries=1, max_workers=2),
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 0.3
    assert list(out["StockID"]) == ["SZ000001", "SH600000"]


def test_query_infotable_updates_progress_for_completed_batches(monkeypatch):
    import tinydata.infotable as infotable_module

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

    monkeypatch.setattr(infotable_module, "_create_progress_tracker", fake_create_progress_tracker)

    out = query_infotable(
        FakeClient(),
        10,
        codes=["000001.SZ", "600000.SH"],
        options=InfoTableOptions(code_batch_size=1, retries=1, max_workers=2, progress=True),
    )

    assert captured["enabled"] is True
    assert captured["total"] == 2
    assert captured["description"] == "infotable 10 batches"
    assert captured["updates"] == [1, 1]
    assert captured["entered"] is True
    assert captured["closed"] is True
    assert list(out["StockID"]) == ["SZ000001", "SH600000"]


def test_query_infotable_reduces_max_workers_after_rate_limit(caplog):
    class RateLimitedClient:
        def __init__(self):
            self.lock = threading.Lock()
            self.active = 0
            self.max_active = 0

        def exec(self, tsl_code, *, as_dataframe=True, timeout_ms=None):
            with self.lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                current = self.active
            time.sleep(0.02)
            with self.lock:
                self.active -= 1
            if current > 1:
                raise TinyDataRateLimitError("HTTP 429")
            code = "SZ000001" if "'SZ000001'" in tsl_code else "SH600000"
            return pd.DataFrame({"StockID": [code], "value": [1]})

    client = RateLimitedClient()
    out = query_infotable(
        client,
        10,
        codes=["000001.SZ", "600000.SH"],
        options=InfoTableOptions(code_batch_size=1, retries=1, max_workers=2),
    )

    assert client.max_active >= 2
    assert "retrying 1 failed batch(es) with max_workers=1" in caplog.text.lower()
    assert list(out["StockID"]) == ["SZ000001", "SH600000"]


def test_query_infotable_rejects_invalid_max_workers():
    with pytest.raises(TinyDataParameterError, match="max_workers"):
        query_infotable(
            FakeClient(),
            10,
            codes=["000001.SZ"],
            options=InfoTableOptions(code_batch_size=1, retries=1, max_workers=0),
        )


def test_tinysoft_yyyymmdd_dates_are_not_parsed_as_unix_ns():
    assert parse_tinysoft_date("20240517").strftime("%Y%m%d") == "20240517"
    assert build_where_clause(date_field="截止日", start_date="20240517", end_date="20240517") == (
        '["截止日"]>=20240517 and ["截止日"]<=20240517'
    )

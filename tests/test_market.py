from __future__ import annotations

import threading
import time

import pandas as pd
import pytest

from tinydata.client import TinyClient
from tinydata.errors import TinyDataParameterError, TinyDataQueryError, TinyDataRateLimitError
from tinydata.market import query_market_panel


class FakeMarketClient:
    def __init__(self):
        self.calls = []

    def query_panel(self, **kwargs):
        self.calls.append(kwargs)
        rows = []
        for code in kwargs["stocks"]:
            rows.append(
                {
                    "date": "2026-05-21 00:00:00",
                    "StockID": code,
                    "open": "10.0",
                    "high": "11.0",
                    "low": "9.5",
                    "close": "10.5",
                    "vol": "1000",
                    "amount": "10500",
                }
            )
        return pd.DataFrame(rows)


def test_markettable_panel_tsl_uses_array_selector_and_week_cycle():
    tsl = TinyClient._build_markettable_panel_tsl(
        stocks=["000001.SZ", "600000.SH"],
        cycle="周线",
        begin_time="20260501",
        end_time="20260522",
        fields=["date", "StockID", "close"],
        code_kind="stock",
    )

    assert "setsysparam(pn_cycle(),cy_week());" in tsl
    assert "of array('SZ000001','SH600000') end;" in tsl


def test_markettable_panel_tsl_sets_adjust_params():
    tsl = TinyClient._build_markettable_panel_tsl(
        stocks=["000001.SZ"],
        cycle="日线",
        begin_time="20260501",
        end_time="20260522",
        fields=["date", "StockID", "close"],
        code_kind="stock",
        adjust="复杂复权",
        adjust_date="20260522",
    )

    assert "setsysparam(Pn_rate(),2);" in tsl
    assert "SetSysParam(Pn_rateday(),20260522T);" in tsl


def test_markettable_panel_tsl_defaults_adjust_date_to_end_time():
    tsl = TinyClient._build_markettable_panel_tsl(
        stocks=["000001.SZ"],
        cycle="日线",
        begin_time="20260501",
        end_time="20260522",
        fields=["date", "StockID", "close"],
        code_kind="stock",
        adjust="ratio",
    )

    assert "setsysparam(Pn_rate(),1);" in tsl
    assert "SetSysParam(Pn_rateday(),20260522T);" in tsl


def test_markettable_panel_tsl_accepts_rateday_sentinels():
    backward = TinyClient._build_markettable_panel_tsl(
        stocks=["000001.SZ"],
        cycle="日线",
        begin_time="20260501",
        end_time="20260522",
        fields=["date", "StockID", "close"],
        code_kind="stock",
        adjust="ratio",
        adjust_date=-1,
    )
    forward = TinyClient._build_markettable_panel_tsl(
        stocks=["000001.SZ"],
        cycle="日线",
        begin_time="20260501",
        end_time="20260522",
        fields=["date", "StockID", "close"],
        code_kind="stock",
        adjust="ratio",
        adjust_date=0,
    )

    assert "SetSysParam(Pn_rateday(),-1);" in backward
    assert "SetSysParam(Pn_rateday(),0);" in forward


def test_query_market_panel_batches_and_normalizes_fields():
    client = FakeMarketClient()

    out = query_market_panel(
        codes=["000001.SZ", "600000.SH"],
        start_date="20260521",
        end_date="20260521",
        code_kind="stock",
        code_batch_size=2,
        cache=False,
        client=client,
    )

    assert client.calls[0]["stocks"] == ["SZ000001", "SH600000"]
    assert list(out["ts_code"]) == ["000001.SZ", "600000.SH"]
    assert out.loc[0, "trade_date"].isoformat() == "2026-05-21"
    assert float(out.loc[0, "close"]) == 10.5
    assert "volume" in out.columns


def test_query_market_panel_normalizes_hk_codes():
    client = FakeMarketClient()

    out = query_market_panel(
        codes=["00700.HK"],
        start_date="20260521",
        end_date="20260521",
        code_kind=None,
        cache=False,
        client=client,
    )

    assert client.calls[0]["stocks"] == ["HK00700"]
    assert out.loc[0, "tsl_code"] == "HK00700"
    assert out.loc[0, "ts_code"] == "00700.HK"


def test_query_market_panel_parses_yyyymmdd_trade_dates():
    class CompactDateClient(FakeMarketClient):
        def query_panel(self, **kwargs):
            self.calls.append(kwargs)
            return pd.DataFrame(
                {
                    "date": ["20260521"],
                    "StockID": [kwargs["stocks"][0]],
                    "close": ["10.5"],
                    "vol": ["1000"],
                }
            )

    out = query_market_panel(
        codes=["000001.SZ"],
        start_date="20260521",
        end_date="20260521",
        code_kind="stock",
        cache=False,
        client=CompactDateClient(),
    )

    assert out.loc[0, "trade_date"].isoformat() == "2026-05-21"


def test_query_market_panel_parallel_batches_reduce_wall_time():
    class SlowClient(FakeMarketClient):
        def __init__(self):
            super().__init__()
            self.barrier = threading.Barrier(2)

        def query_panel(self, **kwargs):
            try:
                self.barrier.wait(timeout=0.3)
            except threading.BrokenBarrierError:
                pass
            time.sleep(0.05)
            return super().query_panel(**kwargs)

    client = SlowClient()
    started = time.perf_counter()
    out = query_market_panel(
        codes=["000001.SZ", "600000.SH"],
        start_date="20260521",
        end_date="20260521",
        code_kind="stock",
        code_batch_size=1,
        max_workers=2,
        cache=False,
        client=client,
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 0.3
    assert list(out["ts_code"]) == ["000001.SZ", "600000.SH"]


def test_query_market_panel_reduces_max_workers_after_rate_limit(monkeypatch, caplog):
    import tinydata.market as market_module

    lock = threading.Lock()
    state = {"active": 0, "max_active": 0, "calls": []}

    def fake_fetch_market_batch(
        client,
        *,
        codes,
        cycle,
        start_time,
        end_time,
        fields,
        code_kind,
        timeout_ms,
        adjust,
        adjust_date,
    ):
        with lock:
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
            current = state["active"]
            state["calls"].append(tuple(codes))
        time.sleep(0.02)
        with lock:
            state["active"] -= 1
        if current > 1:
            raise TinyDataRateLimitError("HTTP 429")
        return pd.DataFrame(
            {
                "date": ["2026-05-21 00:00:00"],
                "StockID": [codes[0]],
                "close": ["10.5"],
                "vol": ["1000"],
            }
        )

    monkeypatch.setattr(market_module, "_fetch_market_batch", fake_fetch_market_batch)

    out = market_module.query_market_panel(
        codes=["000001.SZ", "600000.SH"],
        start_date="20260521",
        end_date="20260521",
        code_kind="stock",
        fields=["trade_date", "ts_code", "close", "volume"],
        code_batch_size=1,
        max_workers=2,
        cache=False,
        client=FakeMarketClient(),
    )

    assert state["max_active"] >= 2
    assert "retrying 1 failed batch(es) with max_workers=1" in caplog.text.lower()
    assert list(out["ts_code"]) == ["000001.SZ", "600000.SH"]


def test_fetch_market_batch_propagates_rate_limit_without_single_fallback(monkeypatch):
    import tinydata.market as market_module

    calls = []

    def fake_exec_market_batch(
        client,
        *,
        codes,
        cycle,
        start_time,
        end_time,
        fields,
        code_kind,
        timeout_ms,
        adjust=None,
        adjust_date=None,
        retries=2,
    ):
        calls.append(list(codes))
        raise TinyDataRateLimitError("HTTP 429")

    monkeypatch.setattr(market_module, "_exec_market_batch", fake_exec_market_batch)

    with pytest.raises(TinyDataRateLimitError, match="429"):
        market_module._fetch_market_batch(
            FakeMarketClient(),
            codes=["SZ000001", "SH600000"],
            cycle="日线",
            start_time="20260521",
            end_time="20260521",
            fields=("date", "StockID", "close"),
            code_kind="stock",
            timeout_ms=None,
        )

    assert calls == [["SZ000001", "SH600000"]]


def test_query_market_panel_codes_none_uses_active_stock_universe(monkeypatch):
    import tinydata.market as market_module

    captured = {}

    def fake_resolve_universe(kind, **kwargs):
        captured["kind"] = kind
        captured["kwargs"] = kwargs
        return ["SZ000001"]

    monkeypatch.setattr(market_module, "resolve_universe", fake_resolve_universe)

    out = market_module.query_market_panel(
        codes=None,
        start_date="20260521",
        end_date="20260521",
        code_kind="stock",
        cache=False,
        client=FakeMarketClient(),
    )

    assert captured["kind"] == "stock"
    assert captured["kwargs"]["include_inactive"] is False
    assert list(out["ts_code"]) == ["000001.SZ"]


def test_query_market_panel_requires_date_window():
    with pytest.raises(TinyDataParameterError, match="require"):
        query_market_panel(codes=["000001.SZ"], code_kind="stock", cache=False, client=FakeMarketClient())


def test_query_market_panel_rejects_invalid_max_workers():
    with pytest.raises(TinyDataParameterError, match="max_workers"):
        query_market_panel(
            codes=["000001.SZ"],
            start_date="20260521",
            end_date="20260522",
            code_kind="stock",
            max_workers=0,
            cache=False,
            client=FakeMarketClient(),
        )


def test_query_market_panel_updates_progress_for_completed_batches(monkeypatch):
    import tinydata.market as market_module

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

    monkeypatch.setattr(market_module, "_create_progress_tracker", fake_create_progress_tracker)

    out = market_module.query_market_panel(
        codes=["000001.SZ", "600000.SH"],
        start_date="20260521",
        end_date="20260521",
        code_kind="stock",
        code_batch_size=1,
        progress=True,
        cache=False,
        client=FakeMarketClient(),
    )

    assert captured["enabled"] is True
    assert captured["total"] == 2
    assert captured["description"] == "market_panel batches"
    assert captured["updates"] == [1, 1]
    assert captured["entered"] is True
    assert captured["closed"] is True
    assert list(out["ts_code"]) == ["000001.SZ", "600000.SH"]


def test_query_market_panel_cache_key_includes_market_params(monkeypatch):
    captured = {}

    class _Cache:
        def read(self, dataset, key):
            captured["read"] = (dataset, key)
            return None

        def write(self, dataset, key, frame):
            captured["write"] = (dataset, key, frame.copy())

    def fake_make_cache_key(dataset, params):
        captured["cache_params"] = params
        return "market-cache-key"

    monkeypatch.setattr("tinydata.market.CacheManager", lambda: _Cache())
    monkeypatch.setattr("tinydata.market.make_cache_key", fake_make_cache_key)

    query_market_panel(
        codes=["000001.SZ"],
        start_date="20260521",
        end_date="20260522",
        cycle="日线",
        fields=["close"],
        code_kind="stock",
        cache=True,
        client=FakeMarketClient(),
    )

    assert captured["cache_params"]["codes"] == ["SZ000001"]
    assert captured["cache_params"]["cycle"] == "日线"
    assert captured["cache_params"]["fields"] == ("date", "StockID", "close")


def test_query_market_panel_passes_adjust_params_and_cache_key(monkeypatch):
    captured = {}

    class _Cache:
        def read(self, dataset, key):
            return None

        def write(self, dataset, key, frame):
            pass

    def fake_make_cache_key(dataset, params):
        captured["cache_params"] = params
        return "market-adjust-cache-key"

    monkeypatch.setattr("tinydata.market.CacheManager", lambda: _Cache())
    monkeypatch.setattr("tinydata.market.make_cache_key", fake_make_cache_key)

    client = FakeMarketClient()
    query_market_panel(
        codes=["000001.SZ"],
        start_date="20260521",
        end_date="20260522",
        cycle="日线",
        code_kind="stock",
        adjust="比例复权",
        cache=True,
        client=client,
    )

    assert client.calls[0]["adjust"] == 1
    assert client.calls[0]["adjust_date"] == "20260522"
    assert captured["cache_params"]["adjust"] == 1
    assert captured["cache_params"]["adjust_date"] == "20260522"


def test_query_market_panel_falls_back_to_single_codes_after_batch_failure():
    class BatchFailClient(FakeMarketClient):
        def query_panel(self, **kwargs):
            self.calls.append(kwargs)
            if len(kwargs["stocks"]) > 1:
                raise TinyDataQueryError("batch rejected")
            rows = []
            for code in kwargs["stocks"]:
                rows.append(
                    {
                        "date": "2026-05-21 00:00:00",
                        "StockID": code,
                        "open": "10.0",
                        "high": "11.0",
                        "low": "9.5",
                        "close": "10.5",
                        "vol": "1000",
                        "amount": "10500",
                    }
                )
            return pd.DataFrame(rows)

    client = BatchFailClient()
    out = query_market_panel(
        codes=["000001.SZ", "600000.SH"],
        start_date="20260521",
        end_date="20260521",
        code_kind="stock",
        code_batch_size=2,
        cache=False,
        client=client,
    )

    assert [call["stocks"] for call in client.calls] == [
        ["SZ000001", "SH600000"],
        ["SZ000001", "SH600000"],
        ["SZ000001"],
        ["SH600000"],
    ]
    assert list(out["ts_code"]) == ["000001.SZ", "600000.SH"]


def test_query_market_panel_rejects_reversed_date_range():
    with pytest.raises(TinyDataParameterError, match="after"):
        query_market_panel(
            codes=["000001.SZ"],
            start_date="20260522",
            end_date="20260521",
            code_kind="stock",
            cache=False,
            client=FakeMarketClient(),
        )


def test_query_market_panel_rejects_unknown_adjust_value():
    with pytest.raises(TinyDataParameterError, match="Unsupported Tinysoft adjust"):
        query_market_panel(
            codes=["000001.SZ"],
            start_date="20260521",
            end_date="20260522",
            code_kind="stock",
            adjust="qfq",
            cache=False,
            client=FakeMarketClient(),
        )


def test_query_market_panel_rejects_adjust_date_without_adjust():
    with pytest.raises(TinyDataParameterError, match="adjust_date requires adjust"):
        query_market_panel(
            codes=["000001.SZ"],
            start_date="20260521",
            end_date="20260522",
            code_kind="stock",
            adjust_date="20260522",
            cache=False,
            client=FakeMarketClient(),
        )


def test_hk_connect_exchange_rate_executes_fixed_functions(monkeypatch):
    import tinydata.market as market_module

    captured = {}

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            captured["tsl"] = tsl
            captured["as_dataframe"] = as_dataframe
            return [0.8991, 0.9547, 0.9269, 0.92681, 0.92699, 0.9269]

    monkeypatch.setattr(market_module, "TinyClient", lambda: _Client())

    out = market_module.hk_connect_exchange_rate(codes=["FXHGTCNY"], trade_date="20240520", cache=False)

    assert "setsysparam(pn_stock(),'FXHGTCNY')" in captured["tsl"]
    assert "setsysparam(pn_date(),20240520T)" in captured["tsl"]
    assert "StockGGTExBuyPrice()" in captured["tsl"]
    assert "StockGGTExMiddleRate()" in captured["tsl"]
    assert captured["as_dataframe"] is False
    assert out.loc[0, "fx_code"] == "FXHGTCNY"
    assert out.loc[0, "trade_date"].isoformat() == "2024-05-20"
    assert float(out.loc[0, "reference_buy_rate"]) == 0.8991
    assert float(out.loc[0, "settlement_buy_rate"]) == 0.92681
    assert out.loc[0, "source_table_name"] == "港股通参考/结算汇率"


def test_hk_connect_exchange_rate_validates_inputs():
    import tinydata.market as market_module

    with pytest.raises(TinyDataParameterError, match="requires trade_date"):
        market_module.hk_connect_exchange_rate(cache=False)
    with pytest.raises(TinyDataParameterError, match="only supports"):
        market_module.hk_connect_exchange_rate(codes=["FXUSDCNY"], trade_date="20240520", cache=False)


def test_query_market_panel_accepts_user_facing_field_aliases(monkeypatch):
    captured = {}

    class AliasClient(FakeMarketClient):
        def query_panel(self, **kwargs):
            captured["fields"] = kwargs["fields"]
            return super().query_panel(**kwargs)

    out = query_market_panel(
        codes=["000001.SZ"],
        start_date="20260521",
        end_date="20260521",
        code_kind="stock",
        fields=["trade_date", "ts_code", "volume", "close"],
        cache=False,
        client=AliasClient(),
    )

    assert captured["fields"] == ("date", "StockID", "vol", "close")
    assert "volume" in out.columns
    assert out.loc[0, "ts_code"] == "000001.SZ"


def test_market_api_consumes_report_period_as_single_day(monkeypatch):
    import tinydata.market as market_module

    captured = {}

    def fake_query_market_panel(**kwargs):
        captured.update(kwargs)
        return pd.DataFrame()

    monkeypatch.setattr(market_module, "query_market_panel", fake_query_market_panel)

    market_module.stock_daily(codes=["000001.SZ"], report_period="20260521", cache=False)

    assert captured["trade_date"] == "20260521"
    assert captured["code_batch_size"] == 300


def test_market_api_passes_max_workers(monkeypatch):
    import tinydata.market as market_module

    captured = {}

    def fake_query_market_panel(**kwargs):
        captured.update(kwargs)
        return pd.DataFrame()

    monkeypatch.setattr(market_module, "query_market_panel", fake_query_market_panel)

    market_module.stock_daily(
        codes=["000001.SZ"],
        start_date="20260521",
        end_date="20260522",
        cache=False,
        max_workers=4,
    )

    assert captured["max_workers"] == 4


def test_market_api_passes_progress(monkeypatch):
    import tinydata.market as market_module

    captured = {}

    def fake_query_market_panel(**kwargs):
        captured.update(kwargs)
        return pd.DataFrame()

    monkeypatch.setattr(market_module, "query_market_panel", fake_query_market_panel)

    market_module.stock_daily(
        codes=["000001.SZ"],
        start_date="20260521",
        end_date="20260522",
        cache=False,
        progress=True,
    )

    assert captured["progress"] is True


def test_realtime_bar_queries_recent_window_without_cache(monkeypatch):
    import tinydata.market as market_module

    captured = {}

    def fake_query_market_panel(**kwargs):
        captured.update(kwargs)
        return pd.DataFrame({"ok": [1]})

    monkeypatch.setattr(market_module, "query_market_panel", fake_query_market_panel)

    out = market_module.realtime_bar(
        ["000001.SZ"],
        end_time="2026-05-21 10:05:00",
        window_minutes=5,
        fields=["close"],
        max_workers=2,
        progress=True,
    )

    assert out.to_dict("records") == [{"ok": 1}]
    assert captured["codes"] == ["SZ000001"]
    assert captured["start_time"] == pd.Timestamp("2026-05-21 10:00:00")
    assert captured["end_time"] == pd.Timestamp("2026-05-21 10:05:00")
    assert captured["cycle"] == "1分钟线"
    assert captured["fields"] == ["close"]
    assert captured["code_kind"] == "stock"
    assert captured["cache"] is False
    assert captured["refresh"] is True
    assert captured["dataset"] == "realtime_bar"
    assert captured["max_workers"] == 2
    assert captured["progress"] is True


def test_realtime_bar_requires_explicit_codes():
    import tinydata.market as market_module

    with pytest.raises(TinyDataParameterError, match="requires one or more codes"):
        market_module.realtime_bar([])


def test_realtime_bar_rejects_invalid_window():
    import tinydata.market as market_module

    with pytest.raises(TinyDataParameterError, match="window_minutes"):
        market_module.realtime_bar(["000001.SZ"], window_minutes=0)


def test_realtime_snapshot_keeps_latest_row_per_requested_code(monkeypatch):
    import tinydata.market as market_module

    captured = {}

    def fake_realtime_bar(codes, **kwargs):
        captured["codes"] = codes
        captured["kwargs"] = kwargs
        return pd.DataFrame(
            {
                "trade_time": pd.to_datetime(
                    [
                        "2026-05-21 09:31:00",
                        "2026-05-21 09:30:00",
                        "2026-05-21 09:32:00",
                        "2026-05-21 09:29:00",
                    ]
                ),
                "tsl_code": ["SZ000001", "SH600000", "SH600000", "SZ000001"],
                "ts_code": ["000001.SZ", "600000.SH", "600000.SH", "000001.SZ"],
                "close": [10.6, 20.1, 20.2, 10.5],
            }
        )

    monkeypatch.setattr(market_module, "realtime_bar", fake_realtime_bar)

    out = market_module.realtime_snapshot(
        ["600000.SH", "000001.SZ"],
        end_time="2026-05-21 10:00:00",
        window_minutes=60,
        fields=["close"],
        max_workers=2,
    )

    assert captured["codes"] == ["600000.SH", "000001.SZ"]
    assert captured["kwargs"]["window_minutes"] == 60
    assert captured["kwargs"]["fields"] == ["close"]
    assert captured["kwargs"]["max_workers"] == 2
    assert list(out["tsl_code"]) == ["SH600000", "SZ000001"]
    assert list(out["close"]) == [20.2, 10.6]
    assert "_tinydata_order" not in out.columns

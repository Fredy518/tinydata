from __future__ import annotations

import threading
import time

import pandas as pd
import pytest

from tinydata.client import TinyClient
from tinydata.errors import TinyDataParameterError, TinyDataQueryError
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

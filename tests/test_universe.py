from __future__ import annotations

import pandas as pd

from tinydata import universe


class _Cache:
    def __init__(self):
        self.frame = None

    def read(self, dataset, key, *, namespace="dataset"):
        return self.frame

    def write(self, dataset, key, frame, *, namespace="dataset"):
        self.frame = frame.copy()


def test_fund_codes_use_opi_table_and_cache(monkeypatch):
    cache = _Cache()
    calls = []

    class _Client:
        def exec(self, tsl, **kwargs):
            calls.append(tsl)
            return pd.DataFrame({"StockID": ["OF000001", "OF000002"]})

    def fake_tiny_client():
        return _Client()

    def fail_query_infotable(*args, **kwargs):
        raise AssertionError("fund_codes should use GetBk block selector before full-table InfoTable")

    def fake_query_infotable(client, table_id, **kwargs):
        fail_query_infotable()
        return pd.DataFrame({"StockID": ["OF000001", "OF000002"]})

    monkeypatch.setattr(universe, "CacheManager", lambda: cache)
    monkeypatch.setattr(universe, "TinyClient", fake_tiny_client)
    monkeypatch.setattr(universe, "query_infotable", fake_query_infotable)

    assert universe.fund_codes(refresh=True) == ["OF000001", "OF000002"]
    assert universe.fund_codes(refresh=False) == ["OF000001", "OF000002"]
    assert len(calls) == 1
    assert "GetBk('开放式基金')" in calls[0]


def test_stock_codes_use_full_basic_table_for_historical_universe(monkeypatch):
    cache = _Cache()
    captured = {}

    def fake_query_infotable(client, table_id, **kwargs):
        captured["table_id"] = table_id
        captured["kwargs"] = kwargs
        return pd.DataFrame(
            {
                "StockID": ["SZ000001", "SH600000", "SZ000002"],
                "当前状态": ["上市", "终止上市", "正常"],
            }
        )

    monkeypatch.setattr(universe, "CacheManager", lambda: cache)
    monkeypatch.setattr(universe, "query_infotable", fake_query_infotable)

    assert universe.stock_codes(refresh=True, include_inactive=True) == ["SZ000001", "SH600000", "SZ000002"]
    assert captured["table_id"] == 10
    assert captured["kwargs"]["allow_full_table"] is True


def test_stock_codes_active_universe_uses_current_board(monkeypatch):
    monkeypatch.setattr(universe, "CacheManager", lambda: _Cache())

    def fail_query_infotable(*args, **kwargs):
        raise AssertionError("include_inactive=False should not use full-table InfoTable")

    class _Client:
        def exec(self, tsl, **kwargs):
            assert "GetBk('A股')" in tsl
            return pd.DataFrame(
                {
                    "StockID": ["SZ000001", "SH600000", "SZ000002"],
                    "当前状态": ["上市", "终止上市", "正常"],
                }
            )

    monkeypatch.setattr(universe, "query_infotable", fail_query_infotable)
    monkeypatch.setattr(universe, "TinyClient", lambda: _Client())

    assert universe.stock_codes(refresh=True, include_inactive=False) == ["SZ000001", "SZ000002"]


def test_market_codes_include_domestic_futures_calendar():
    assert "QI000001" in universe.market_codes()


def test_fof_universe_filters_fund_basic_text(monkeypatch):
    monkeypatch.setattr(universe, "CacheManager", lambda: _Cache())

    class _Client:
        def exec(self, tsl, **kwargs):
            assert "GetBk('开放式基金')" in tsl
            return pd.DataFrame(
                {
                    "StockID": ["OF000001", "OF000002"],
                    "基金类型": ["混合型", "FOF"],
                    "基金名称": ["普通基金", "养老目标基金中基金"],
                }
            )

    monkeypatch.setattr(universe, "TinyClient", lambda: _Client())

    assert universe.fof_fund_codes(refresh=True) == ["OF000002"]


def test_fund_market_codes_use_trading_fund_blocks(monkeypatch):
    monkeypatch.setattr(universe, "CacheManager", lambda: _Cache())
    calls = []

    class _Client:
        def exec(self, tsl, **kwargs):
            calls.append(tsl)
            if "GetBk('上证基金')" in tsl:
                return pd.DataFrame({"StockID": ["SH510300", "OF000001"], "清算日": [None, None]})
            if "GetBk('深证基金')" in tsl:
                return pd.DataFrame({"StockID": ["SZ159919"], "清算日": [None]})
            raise RuntimeError("block unavailable")

    monkeypatch.setattr(universe, "TinyClient", lambda: _Client())

    assert universe.fund_market_codes(refresh=True) == ["SH510300", "SZ159919"]
    assert any("GetBk('上证基金')" in call for call in calls)
    assert any("GetBk('深证基金')" in call for call in calls)


def test_future_codes_normalize_contract_series(monkeypatch):
    monkeypatch.setattr(universe, "CacheManager", lambda: _Cache())

    class _Client:
        def exec(self, tsl, **kwargs):
            assert "GetBk('股指期货')" in tsl
            return pd.DataFrame({"合约代码": ["IF2406.CFX", "IC2406.CFX"]})

    monkeypatch.setattr(universe, "TinyClient", lambda: _Client())

    assert universe.future_codes(refresh=True) == ["IF2406", "IC2406"]


def test_option_codes_normalize_contract_series(monkeypatch):
    monkeypatch.setattr(universe, "CacheManager", lambda: _Cache())
    calls = []

    class _Client:
        def exec(self, tsl, **kwargs):
            calls.append(tsl)
            return pd.DataFrame(
                {
                    "合约交易代码": ["10000001.SH", "90000001.SZ"],
                    "上市地": ["上海证券交易所", "深圳证券交易所"],
                    "截止日": ["20240517", "20240517"],
                }
            )

    monkeypatch.setattr(universe, "TinyClient", lambda: _Client())

    assert universe.option_codes(refresh=True, trade_date="20240517") == ["10000001", "90000001"]
    assert any("GetBk('ETF期权')" in call for call in calls)

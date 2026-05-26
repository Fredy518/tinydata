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

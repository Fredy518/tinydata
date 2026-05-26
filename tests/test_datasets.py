from __future__ import annotations

import pandas as pd

from tinydata.datasets.fund import FUND_FOF_HOLDING_DETAIL
from tinydata.datasets.stock import STOCK_FINA_PIT_EXT
from tinydata.datasets import specs as specs_module
from tinydata.datasets.specs import fetch_dataset, process_dataset_frame


def test_process_dataset_frame_maps_fields_and_types():
    raw = pd.DataFrame(
        {
            "StockID": ["OF012345"],
            "截止日": ["20231231"],
            "代码": ["OF000001"],
            "数量": ["100.5"],
            "市值排名": ["1"],
            "未映射中文列": ["drop-me"],
        }
    )

    out = process_dataset_frame(raw, FUND_FOF_HOLDING_DETAIL)
    assert out.loc[0, "ts_code"] == "012345.OF"
    assert out.loc[0, "report_date"].isoformat() == "2023-12-31"
    assert out.loc[0, "holding_code_raw"] == "OF000001"
    assert float(out.loc[0, "quantity"]) == 100.5
    assert int(out.loc[0, "rank_no"]) == 1
    assert out.loc[0, "source_table_id"] == 349
    assert "未映射中文列" not in out.columns


def test_process_dataset_frame_parses_yyyymmdd_dates():
    raw = pd.DataFrame({"StockID": ["OF012345"], "截止日": [20240517]})
    out = process_dataset_frame(raw, FUND_FOF_HOLDING_DETAIL)
    assert out.loc[0, "report_date"].isoformat() == "2024-05-17"


def test_fetch_dataset_passes_projected_fields_and_caches_field_list(monkeypatch):
    captured = {}

    class _Cache:
        def read(self, dataset, key):
            captured["read"] = (dataset, key)
            return None

        def write(self, dataset, key, frame):
            captured["write"] = (dataset, key, frame.copy())

    def fake_make_cache_key(dataset, params):
        captured["cache_params"] = params
        return "cache-key"

    def fake_query_infotable(client, table_id, **kwargs):
        captured["query_kwargs"] = kwargs
        return pd.DataFrame(
            {
                "StockID": ["OF012345"],
                "截止日": ["20231231"],
                "代码": ["OF000001"],
                "数量": ["100.5"],
                "市值排名": ["1"],
            }
        )

    monkeypatch.setattr(specs_module, "CacheManager", lambda: _Cache())
    monkeypatch.setattr(specs_module, "make_cache_key", fake_make_cache_key)
    monkeypatch.setattr(specs_module, "query_infotable", fake_query_infotable)

    out = fetch_dataset(
        FUND_FOF_HOLDING_DETAIL,
        client=object(),
        codes=["012345.OF"],
        report_period="20231231",
    )

    assert out.loc[0, "ts_code"] == "012345.OF"
    assert captured["query_kwargs"]["fields"] == (
        "StockID",
        "StockName",
        "截止日",
        "名称",
        "代码",
        "数量",
        "市值",
        "占净值比例(%)",
        "市值排名",
        "是否属于关联基金",
    )
    assert captured["cache_params"]["fields"] == captured["query_kwargs"]["fields"]


def test_fetch_dataset_fields_accept_source_or_mapped_names(monkeypatch):
    def fake_query_infotable(client, table_id, **kwargs):
        return pd.DataFrame(
            {
                "StockID": ["OF012345"],
                "截止日": ["20231231"],
                "代码": ["OF000001"],
                "数量": ["100.5"],
            }
        )

    monkeypatch.setattr(specs_module, "query_infotable", fake_query_infotable)

    source_out = fetch_dataset(
        FUND_FOF_HOLDING_DETAIL,
        client=object(),
        codes=["012345.OF"],
        report_period="20231231",
        fields=["代码"],
        cache=False,
    )
    mapped_out = fetch_dataset(
        FUND_FOF_HOLDING_DETAIL,
        client=object(),
        codes=["012345.OF"],
        report_period="20231231",
        fields=["holding_code_raw"],
        cache=False,
    )

    assert source_out.loc[0, "holding_code_raw"] == "OF000001"
    assert mapped_out.loc[0, "holding_code_raw"] == "OF000001"
    assert "quantity" not in source_out.columns


def test_fina_pit_postprocess_vectorizes_metric_rows():
    raw = pd.DataFrame(
        {
            "StockID": ["SZ000001", "SZ000002"],
            "截止日": ["20231231", "20231231"],
            "公布日": ["20240420", "20240421"],
            "每股收益(摊薄)": [1.2, None],
            "每股净资产": [12.3, 8.8],
        }
    )

    out = process_dataset_frame(raw, STOCK_FINA_PIT_EXT)

    assert list(out["metric_name"]) == ["eps_diluted", "bps", "bps"]
    assert set(out["metric_field_id"].astype(int)) == {42002, 42006}
    assert out.loc[0, "trade_date"].isoformat() == "2024-04-20"

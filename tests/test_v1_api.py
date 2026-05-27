from __future__ import annotations

import pandas as pd
import pytest
import inspect

import tinydata as td
from tinydata.datasets import fund as fund_module
from tinydata.datasets import index as index_module
from tinydata.datasets import specs as specs_module
from tinydata.datasets.fund import FUND_STOCK_HOLDING_DETAIL
from tinydata.datasets.specs import fetch_dataset
from tinydata.errors import TinyDataCodePoolError, TinyDataParameterError


def test_v1_metadata_lists_expanded_dataset_surface():
    datasets = td.list_datasets()
    names = set(datasets["name"])

    assert td.__version__ == "1.2.0"
    assert "stock_hsgt_daily" in names
    assert "fund_cbond_holding_detail" in names
    assert "index_member_versioned" in names
    assert "stock_daily" in names
    assert "fund_nav" in names
    assert "fina_income" in names
    assert td.get_dataset_info("fund_fof_holding_detail")["table_id"] == 349
    assert td.get_dataset_info("stock_daily")["source_kind"] == "market"
    assert td.get_dataset_info("stock_daily")["code_batch_size"] == 300
    assert td.get_dataset_info("fund_classification_info")["code_kind"] is None
    assert td.get_dataset_info("fund_daily")["code_kind"] == "fund_market"


def test_high_volume_dataset_requires_date_window():
    with pytest.raises(TinyDataParameterError, match="high-volume"):
        fetch_dataset(FUND_STOCK_HOLDING_DETAIL, codes=["000001.OF"], cache=False)


def test_all_history_is_explicit_escape_hatch(monkeypatch):
    captured = {}

    def fake_query_infotable(client, table_id, **kwargs):
        captured["kwargs"] = kwargs
        return pd.DataFrame({"StockID": ["OF000001"], "截止日": ["20231231"], "代码": ["SH600000"]})

    monkeypatch.setattr("tinydata.datasets.specs.query_infotable", fake_query_infotable)

    out = fetch_dataset(
        FUND_STOCK_HOLDING_DETAIL,
        client=object(),
        codes=["000001.OF"],
        all_history=True,
        cache=False,
    )

    assert captured["kwargs"]["codes"] == ["OF000001"]
    assert out.loc[0, "security_code_raw"] == "SH600000"


def test_public_query_infotable_requires_explicit_full_table(monkeypatch):
    monkeypatch.setattr(td, "get_client", lambda: object())

    with pytest.raises(TinyDataCodePoolError):
        td.query_infotable(10)


def test_public_query_infotable_allows_explicit_full_table(monkeypatch):
    captured = {}

    def fake_query_infotable(client, table_id, **kwargs):
        captured["client"] = client
        captured["table_id"] = table_id
        captured["kwargs"] = kwargs
        return pd.DataFrame()

    monkeypatch.setattr(td, "get_client", lambda: object())
    monkeypatch.setattr(td, "_query_infotable", fake_query_infotable)

    td.query_infotable(10, allow_full_table=True)

    assert captured["table_id"] == 10
    assert captured["kwargs"]["allow_full_table"] is True


def test_public_query_infotable_passes_parallel_options(monkeypatch):
    captured = {}

    def fake_query_infotable(client, table_id, **kwargs):
        captured["table_id"] = table_id
        captured["kwargs"] = kwargs
        return pd.DataFrame()

    monkeypatch.setattr(td, "get_client", lambda: object())
    monkeypatch.setattr(td, "_query_infotable", fake_query_infotable)

    td.query_infotable(
        10,
        codes=["000001.SZ"],
        code_batch_size=50,
        max_workers=4,
        progress=True,
    )

    assert captured["table_id"] == 10
    assert captured["kwargs"]["options"].code_batch_size == 50
    assert captured["kwargs"]["options"].max_workers == 4
    assert captured["kwargs"]["options"].progress is True


def test_interactive_default_progress_uses_auto_mode_in_public_signatures():
    assert inspect.signature(td.stock_daily).parameters["progress"].default is None
    assert inspect.signature(td.query_infotable).parameters["progress"].default is None


def test_first_priority_stock_dataset_api_passes_parallel_options(monkeypatch):
    captured = {}

    def fake_fetch_dataset(spec, **kwargs):
        captured["spec_name"] = spec.name
        captured["kwargs"] = kwargs
        return pd.DataFrame()

    monkeypatch.setattr(specs_module, "fetch_dataset", fake_fetch_dataset)

    td.fina_indicator(
        codes=["000001.SZ"],
        report_period="20231231",
        max_workers=4,
        progress=True,
    )

    assert captured["spec_name"] == "fina_indicator"
    assert captured["kwargs"]["max_workers"] == 4
    assert captured["kwargs"]["progress"] is True


def test_first_priority_fund_dataset_api_passes_parallel_options(monkeypatch):
    captured = {}

    def fake_fetch_dataset(spec, **kwargs):
        captured["spec_name"] = spec.name
        captured["kwargs"] = kwargs
        return pd.DataFrame()

    monkeypatch.setattr(specs_module, "fetch_dataset", fake_fetch_dataset)

    td.fund_stock_holding_detail(
        codes=["000001.OF"],
        report_period="20231231",
        max_workers=3,
        progress=True,
    )

    assert captured["spec_name"] == "fund_stock_holding_detail"
    assert captured["kwargs"]["max_workers"] == 3
    assert captured["kwargs"]["progress"] is True


def test_second_priority_index_weight_passes_parallel_options(monkeypatch):
    captured = {}

    def fake_run_parallel_code_queries(codes, **kwargs):
        captured["codes"] = list(codes)
        captured.update(kwargs)
        return []

    monkeypatch.setattr(index_module, "run_parallel_code_queries", fake_run_parallel_code_queries)

    out = td.index_weight(
        codes=["000300.CSI"],
        trade_date="20210107",
        max_workers=4,
        progress=True,
        cache=False,
    )

    assert captured["codes"] == ["CSI000300"]
    assert captured["max_workers"] == 4
    assert captured["progress"] is True
    assert captured["description"] == "index_weight codes"
    assert out.empty


def test_second_priority_index_member_snapshot_passes_parallel_options(monkeypatch):
    captured = {}

    def fake_run_parallel_code_queries(codes, **kwargs):
        captured["codes"] = list(codes)
        captured.update(kwargs)
        return []

    monkeypatch.setattr(index_module, "run_parallel_code_queries", fake_run_parallel_code_queries)

    out = td.index_member_snapshot(
        codes=["000300.CSI"],
        trade_date="20210107",
        max_workers=3,
        progress=True,
        cache=False,
    )

    assert captured["codes"] == ["CSI000300"]
    assert captured["max_workers"] == 3
    assert captured["progress"] is True
    assert captured["description"] == "index_member_snapshot codes"
    assert out.empty


def test_second_priority_fund_etf_constituent_passes_parallel_options(monkeypatch):
    captured = {}

    def fake_run_parallel_code_queries(codes, **kwargs):
        captured["codes"] = list(codes)
        captured.update(kwargs)
        return []

    monkeypatch.setattr(fund_module, "run_parallel_code_queries", fake_run_parallel_code_queries)

    out = td.fund_etf_constituent(
        codes=["510050.OF"],
        trade_date="20210107",
        max_workers=2,
        progress=True,
        cache=False,
    )

    assert captured["codes"] == ["OF510050"]
    assert captured["max_workers"] == 2
    assert captured["progress"] is True
    assert captured["description"] == "fund_etf_constituent codes"
    assert out.empty


def test_second_priority_fund_adjusted_nav_passes_parallel_options(monkeypatch):
    captured = {}

    def fake_run_parallel_code_queries(codes, **kwargs):
        captured["codes"] = list(codes)
        captured.update(kwargs)
        return []

    monkeypatch.setattr(fund_module, "run_parallel_code_queries", fake_run_parallel_code_queries)

    out = td.fund_adjusted_nav(
        codes=["510050.OF"],
        start_date="20210101",
        end_date="20210131",
        max_workers=2,
        progress=True,
        cache=False,
    )

    assert captured["codes"] == ["OF510050"]
    assert captured["max_workers"] == 2
    assert captured["progress"] is True
    assert captured["description"] == "fund_adjusted_nav codes"
    assert out.empty

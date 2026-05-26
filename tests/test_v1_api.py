from __future__ import annotations

import pandas as pd
import pytest

import tinydata as td
from tinydata.datasets.fund import FUND_STOCK_HOLDING_DETAIL
from tinydata.datasets.specs import fetch_dataset
from tinydata.errors import TinyDataParameterError


def test_v1_metadata_lists_expanded_dataset_surface():
    datasets = td.list_datasets()
    names = set(datasets["name"])

    assert td.__version__ == "1.1.0"
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

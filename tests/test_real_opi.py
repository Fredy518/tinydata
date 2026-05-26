from __future__ import annotations

import os
from typing import Callable

import pandas as pd
import pytest

import tinydata as td


pytestmark = [
    pytest.mark.requires_tinysoft,
    pytest.mark.skipif(
        os.environ.get("TINYDATA_RUN_REAL_OPI") != "1",
        reason="set TINYDATA_RUN_REAL_OPI=1 to run real Tinysoft OPI tests",
    ),
]


def _configure_real_opi() -> None:
    td.configure(timeout_ms=30_000, request_interval=0.05)


def _assert_frame(df: pd.DataFrame, required_columns: set[str], *, min_rows: int = 1) -> None:
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) >= required_columns
    assert len(df) >= min_rows


def test_real_opi_markettable_panel_multi_stock_daily():
    _configure_real_opi()

    df = td.query_market_panel(
        codes=["000001.SZ", "600000.SH"],
        start_date="20240520",
        end_date="20240522",
        cycle="日线",
        cache=False,
        refresh=True,
        code_kind="stock",
        code_batch_size=10,
    )

    _assert_frame(df, {"trade_date", "tsl_code", "ts_code", "open", "high", "low", "close", "volume", "amount"}, min_rows=6)
    assert {"000001.SZ", "600000.SH"} <= set(df["ts_code"])


@pytest.mark.parametrize(
    ("name", "func", "kwargs", "required_columns"),
    [
        (
            "stock_basic_ext",
            td.stock_basic_ext,
            {"codes": ["000001.SZ"], "cache": False, "refresh": True},
            {"tsl_code", "ts_code", "company_short_name"},
        ),
        (
            "fund_basic_ext",
            td.fund_basic_ext,
            {"codes": ["000001.OF"], "cache": False, "refresh": True},
            {"tsl_code", "ts_code", "fund_name"},
        ),
        (
            "fund_nav",
            td.fund_nav,
            {"codes": ["000001.OF"], "start_date": "20240520", "end_date": "20240522", "cache": False, "refresh": True},
            {"tsl_code", "ts_code", "trade_date", "unit_nav", "accum_nav"},
        ),
        (
            "fina_income",
            td.fina_income,
            {"codes": ["000001.SZ"], "start_date": "20240101", "end_date": "20241231", "cache": False, "refresh": True},
            {"tsl_code", "ts_code", "report_date", "ann_date", "total_revenue", "parent_net_profit"},
        ),
        (
            "fina_balancesheet",
            td.fina_balancesheet,
            {"codes": ["000001.SZ"], "start_date": "20240101", "end_date": "20241231", "cache": False, "refresh": True},
            {"tsl_code", "ts_code", "report_date", "ann_date", "total_assets", "total_liabilities"},
        ),
        (
            "fina_cashflow",
            td.fina_cashflow,
            {"codes": ["000001.SZ"], "start_date": "20240101", "end_date": "20241231", "cache": False, "refresh": True},
            {"tsl_code", "ts_code", "report_date", "ann_date", "net_operating_cashflow"},
        ),
        (
            "trade_calendar",
            td.trade_calendar,
            {"start_date": "20240520", "end_date": "20240522", "cache": False, "refresh": True},
            {"market_code", "trade_date", "is_trade_day"},
        ),
        (
            "stock_margin",
            td.stock_margin,
            {"trade_date": "20240522", "cache": False, "refresh": True},
            {"market_code", "trade_date", "margin_balance", "margin_short_balance"},
        ),
    ],
)
def test_real_opi_core_datasets(name: str, func: Callable[..., pd.DataFrame], kwargs: dict, required_columns: set[str]):
    _configure_real_opi()

    df = func(**kwargs)

    _assert_frame(df, required_columns, min_rows=1)


def test_real_opi_high_volume_guard_still_blocks_accidental_full_history():
    _configure_real_opi()

    with pytest.raises(td.TinyDataParameterError):
        td.fund_stock_holding_detail(codes=["000001.OF"], cache=False)


@pytest.mark.parametrize(
    ("name", "func", "kwargs"),
    [
        ("stock_weekly", td.stock_weekly, {"codes": ["000001.SZ"], "start_date": "20240401", "end_date": "20240531", "cache": False, "refresh": True}),
        ("stock_monthly", td.stock_monthly, {"codes": ["000001.SZ"], "start_date": "20240101", "end_date": "20240531", "cache": False, "refresh": True}),
        ("fund_daily", td.fund_daily, {"codes": ["510300.SH"], "start_date": "20240520", "end_date": "20240522", "cache": False, "refresh": True}),
        ("index_daily", td.index_daily, {"codes": ["000300.CSI"], "start_date": "20240520", "end_date": "20240522", "cache": False, "refresh": True}),
        ("cbond_daily", td.cbond_daily, {"codes": ["113001.SH"], "start_date": "20240520", "end_date": "20240522", "cache": False, "refresh": True}),
        ("future_daily", td.future_daily, {"codes": ["IF2406"], "start_date": "20240520", "end_date": "20240522", "cache": False, "refresh": True}),
        ("fund_manager_ext", td.fund_manager_ext, {"codes": ["000001.OF"], "start_date": "20200101", "end_date": "20241231", "cache": False, "refresh": True}),
        ("fund_share", td.fund_share, {"codes": ["000001.OF"], "start_date": "20200101", "end_date": "20241231", "cache": False, "refresh": True}),
        ("fund_stock_holding_detail", td.fund_stock_holding_detail, {"codes": ["000001.OF"], "report_period": "20231231", "cache": False, "refresh": True}),
        ("fund_bond_holding_detail", td.fund_bond_holding_detail, {"codes": ["000001.OF"], "report_period": "20231231", "cache": False, "refresh": True}),
        ("fund_asset_alloc", td.fund_asset_alloc, {"codes": ["000001.OF"], "report_period": "20231231", "cache": False, "refresh": True}),
        ("fund_industry_alloc", td.fund_industry_alloc, {"codes": ["000001.OF"], "report_period": "20231231", "cache": False, "refresh": True}),
        ("fund_bond_alloc", td.fund_bond_alloc, {"codes": ["000001.OF"], "report_period": "20231231", "cache": False, "refresh": True}),
        ("fund_holder_structure", td.fund_holder_structure, {"codes": ["000001.OF"], "report_period": "20231231", "cache": False, "refresh": True}),
        ("fund_top_holder", td.fund_top_holder, {"codes": ["000001.OF"], "report_period": "20231231", "cache": False, "refresh": True}),
        ("fina_indicator", td.fina_indicator, {"codes": ["000001.SZ"], "start_date": "20240101", "end_date": "20241231", "cache": False, "refresh": True}),
        ("fina_forecast", td.fina_forecast, {"codes": ["000001.SZ"], "start_date": "20200101", "end_date": "20241231", "cache": False, "refresh": True}),
        ("fina_express", td.fina_express, {"codes": ["000001.SZ"], "start_date": "20200101", "end_date": "20241231", "cache": False, "refresh": True}),
        ("fina_disclosure", td.fina_disclosure, {"codes": ["000001.SZ"], "report_period": "20241231", "cache": False, "refresh": True}),
        ("fina_mainbz", td.fina_mainbz, {"codes": ["000001.SZ"], "report_period": "20231231", "cache": False, "refresh": True}),
        ("stock_namechange", td.stock_namechange, {"codes": ["000001.SZ"], "start_date": "19900101", "end_date": "20241231", "cache": False, "refresh": True}),
        ("stock_sharefloat", td.stock_sharefloat, {"codes": ["000001.SZ"], "start_date": "20200101", "end_date": "20241231", "cache": False, "refresh": True}),
        ("stock_dividend", td.stock_dividend, {"codes": ["000001.SZ"], "start_date": "20200101", "end_date": "20241231", "cache": False, "refresh": True}),
        ("stock_holdernumber", td.stock_holdernumber, {"codes": ["000001.SZ"], "start_date": "20200101", "end_date": "20241231", "cache": False, "refresh": True}),
        ("stock_margindetail", td.stock_margindetail, {"codes": ["000001.SZ"], "trade_date": "20240522", "cache": False, "refresh": True}),
        ("stock_margin_collateral", td.stock_margin_collateral, {"codes": ["000001.SZ"], "trade_date": "20240522", "cache": False, "refresh": True}),
        ("stock_hsgt_daily", td.stock_hsgt_daily, {"trade_date": "20240522", "cache": False, "refresh": True}),
        ("stock_hsgt_top10", td.stock_hsgt_top10, {"codes": ["HG000002"], "trade_date": "20240522", "cache": False, "refresh": True}),
        ("stock_hsgt_hold", td.stock_hsgt_hold, {"codes": ["000001.SZ"], "trade_date": "20240522", "cache": False, "refresh": True}),
        ("stock_lending_balance", td.stock_lending_balance, {"codes": ["000001.SZ"], "trade_date": "20240522", "cache": False, "refresh": True}),
        ("stock_pledge_detail", td.stock_pledge_detail, {"codes": ["000001.SZ"], "trade_date": "20240522", "cache": False, "refresh": True}),
        ("index_basic_ext", td.index_basic_ext, {"codes": ["000300.CSI"], "cache": False, "refresh": True}),
        ("index_member_versioned", td.index_member_versioned, {"codes": ["000300.CSI"], "all_history": True, "cache": False, "refresh": True}),
        ("bond_basic_ext", td.bond_basic_ext, {"codes": ["113001.SH"], "cache": False, "refresh": True}),
        ("future_basic_ext", td.future_basic_ext, {"codes": ["IF2406"], "cache": False, "refresh": True}),
        ("future_product_mapping_ext", td.future_product_mapping_ext, {"codes": ["IF"], "cache": False, "refresh": True}),
    ],
)
def test_real_opi_wide_api_surface_does_not_raise(name: str, func: Callable[..., pd.DataFrame], kwargs: dict):
    _configure_real_opi()

    df = func(**kwargs)

    assert isinstance(df, pd.DataFrame), name

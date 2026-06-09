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


def test_real_opi_stock_ttm_indicator():
    _configure_real_opi()

    df = td.stock_ttm_indicator(
        codes=["000001.SZ"],
        report_period="20230930",
        as_of_date="20231031",
        fields=[
            "total_revenue_ttm",
            "parent_net_profit_ttm",
            "net_operating_cashflow_ttm",
        ],
        cache=False,
        refresh=True,
    )

    _assert_frame(
        df,
        {
            "tsl_code",
            "ts_code",
            "report_date",
            "as_of_date",
            "total_revenue_ttm",
            "parent_net_profit_ttm",
            "net_operating_cashflow_ttm",
        },
    )


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
            "stock_valuation_indicator",
            td.stock_valuation_indicator,
            {"codes": ["000001.SZ"], "report_period": "20231231", "fields": ["roic_pct"], "cache": False, "refresh": True},
            {"tsl_code", "ts_code", "report_date", "roic_pct"},
        ),
        (
            "trade_calendar",
            td.trade_calendar,
            {"start_date": "20240520", "end_date": "20240522", "cache": False, "refresh": True},
            {"market_code", "trade_date", "is_trade_day"},
        ),
        (
            "hk_daily",
            td.hk_daily,
            {"codes": ["00700.HK"], "start_date": "20240520", "end_date": "20240522", "cache": False, "refresh": True},
            {"tsl_code", "ts_code", "trade_date", "open", "high", "low", "close", "volume", "amount"},
        ),
        (
            "hk_connect_exchange_rate",
            td.hk_connect_exchange_rate,
            {"codes": ["FXHGTCNY"], "trade_date": "20240520", "cache": False, "refresh": True},
            {"fx_code", "trade_date", "reference_buy_rate", "reference_sell_rate", "reference_middle_rate", "settlement_buy_rate", "settlement_sell_rate", "settlement_middle_rate"},
        ),
        (
            "future_main_info",
            td.future_main_info,
            {"codes": ["IF"], "all_history": True, "cache": False, "refresh": True},
            {"source_code", "product_code", "main_virtual_code", "change_date", "main_contract_code"},
        ),
        (
            "future_trade_ranking",
            td.future_trade_ranking,
            {"codes": ["IF2606"], "start_date": "20260601", "end_date": "20260608", "ranking_type": "long", "cache": False, "refresh": True},
            {"contract_code_raw", "trade_date", "ranking_type", "ranking_side", "rank_no", "quantity", "member_name"},
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
        ("fund_benchmark", td.fund_benchmark, {"codes": ["502049.SH"], "cache": False, "refresh": True}),
        ("fund_fee", td.fund_fee, {"codes": ["502004.SH"], "cache": False, "refresh": True}),
        ("fund_nav_benchmark_return", td.fund_nav_benchmark_return, {"codes": ["000814.OF"], "report_period": "20231231", "cache": False, "refresh": True}),
        ("fund_balance_sheet", td.fund_balance_sheet, {"codes": ["004905.OF"], "report_period": "20231231", "cache": False, "refresh": True}),
        ("fund_income_statement", td.fund_income_statement, {"codes": ["160127.OF"], "report_period": "20231231", "cache": False, "refresh": True}),
        ("fund_buy_sell", td.fund_buy_sell, {"codes": ["004905.OF"], "report_period": "20231231", "cache": False, "refresh": True}),
        ("fund_dividend", td.fund_dividend, {"codes": ["000001.OF"], "start_date": "20200101", "end_date": "20241231", "cache": False, "refresh": True}),
        ("fund_split", td.fund_split, {"codes": ["160127.OF"], "all_history": True, "cache": False, "refresh": True}),
        ("fund_namechange", td.fund_namechange, {"codes": ["000001.OF"], "cache": False, "refresh": True}),
        ("fund_etf_sub_redemption", td.fund_etf_sub_redemption, {"codes": ["159901.OF"], "start_date": "20100701", "end_date": "20100803", "cache": False, "refresh": True}),
        ("fund_etf_constituent", td.fund_etf_constituent, {"codes": ["510050.OF"], "trade_date": "20190816", "cache": False, "refresh": True}),
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
        ("stock_ipo", td.stock_ipo, {"codes": ["000001.SZ"], "cache": False, "refresh": True}),
        ("stock_classification_info", td.stock_classification_info, {"codes": ["SWHY"], "all_history": True, "cache": False, "refresh": True}),
        ("stock_delist_solution", td.stock_delist_solution, {"codes": ["600087.SH"], "all_history": True, "cache": False, "refresh": True}),
        ("stock_top10_holder", td.stock_top10_holder, {"codes": ["000001.SZ"], "report_period": "20231231", "cache": False, "refresh": True}),
        ("stock_top10_float_holder", td.stock_top10_float_holder, {"codes": ["000001.SZ"], "report_period": "20231231", "cache": False, "refresh": True}),
        ("stock_controller", td.stock_controller, {"codes": ["000001.SZ"], "report_period": "20231231", "cache": False, "refresh": True}),
        ("stock_officer_hold_change", td.stock_officer_hold_change, {"codes": ["000001.SZ"], "start_date": "20200101", "end_date": "20241231", "cache": False, "refresh": True}),
        ("stock_foreign_holding", td.stock_foreign_holding, {"codes": ["603605.SH"], "start_date": "20240101", "end_date": "20241231", "cache": False, "refresh": True}),
        ("stock_nonrecurring", td.stock_nonrecurring, {"codes": ["000001.SZ"], "report_period": "20231231", "cache": False, "refresh": True}),
        ("stock_trade_time", td.stock_trade_time, {"codes": ["000001.SH"], "all_history": True, "cache": False, "refresh": True}),
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
        ("index_member_snapshot", td.index_member_snapshot, {"codes": ["000300.CSI"], "trade_date": "20210107", "cache": False, "refresh": True}),
        ("index_weight", td.index_weight, {"codes": ["000300.CSI"], "trade_date": "20210531", "cache": False, "refresh": True}),
        ("index_valuation", td.index_valuation, {"codes": ["000300.CSI"], "report_period": "20231231", "fields": ["762034"], "cache": False, "refresh": True}),
        ("fund_adjusted_nav", td.fund_adjusted_nav, {"codes": ["510050.OF"], "start_date": "20190101", "end_date": "20190425", "adjust": 1, "adjust_date": -1, "cache": False, "refresh": True}),
        ("bond_basic_ext", td.bond_basic_ext, {"codes": ["113001.SH"], "cache": False, "refresh": True}),
        ("future_basic_ext", td.future_basic_ext, {"codes": ["IF2406"], "cache": False, "refresh": True}),
        ("future_product_mapping_ext", td.future_product_mapping_ext, {"codes": ["IF"], "cache": False, "refresh": True}),
    ],
)
def test_real_opi_wide_api_surface_does_not_raise(name: str, func: Callable[..., pd.DataFrame], kwargs: dict):
    _configure_real_opi()

    df = func(**kwargs)

    assert isinstance(df, pd.DataFrame), name

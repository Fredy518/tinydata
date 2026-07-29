from __future__ import annotations

import pandas as pd
import pytest

from tinydata.datasets import future as future_module
from tinydata.datasets import fund as fund_module
from tinydata.datasets import index as index_module
from tinydata.datasets import stock as stock_module
from tinydata.datasets.fund import FUND_ADJUSTED_NAV, FUND_BALANCE_SHEET, FUND_ETF_CONSTITUENT, FUND_FOF_HOLDING_DETAIL
from tinydata.datasets.future import FUTURE_BASIC_EXT, FUTURE_MAIN_INFO, FUTURE_TRADE_RANKING
from tinydata.datasets.index import INDEX_MEMBER_SNAPSHOT, INDEX_VALUATION, INDEX_WEIGHT
from tinydata.datasets.option import OPTION_BASIC_DAILY_EXT
from tinydata.datasets.stock import (
    STOCK_FINA_PIT_EXT,
    STOCK_IPO,
    STOCK_MARGIN,
    STOCK_MARGINDETAIL,
    STOCK_TRADE_TIME,
    STOCK_VALUATION_INDICATOR,
)
from tinydata.datasets import specs as specs_module
from tinydata.datasets.specs import fetch_dataset, process_dataset_frame
from tinydata.errors import TinyDataParameterError


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


def test_process_dataset_frame_parses_mixed_date_formats():
    raw = pd.DataFrame(
        {
            "StockID": ["OF004905"],
            "截止日": ["2024-05-17 00:00:00"],
            "公布日": [20240518],
            "资产总计": ["100.5"],
        }
    )

    out = process_dataset_frame(raw, FUND_BALANCE_SHEET)

    assert out.loc[0, "report_date"].isoformat() == "2024-05-17"
    assert out.loc[0, "ann_date"].isoformat() == "2024-05-18"


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
    assert captured["query_kwargs"]["date_field"] == "截止日"
    assert captured["query_kwargs"]["as_of_date"] is None


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


def test_fetch_dataset_start_end_sets_as_of_date_for_pit_window(monkeypatch):
    captured = {}

    def fake_query_infotable(client, table_id, **kwargs):
        captured.update(kwargs)
        return pd.DataFrame(
            {
                "StockID": ["SZ000001"],
                "截止日": ["20231231"],
                "公布日": ["20240420"],
                "每股收益(摊薄)": [1.2],
            }
        )

    monkeypatch.setattr(specs_module, "query_infotable", fake_query_infotable)

    out = fetch_dataset(
        STOCK_FINA_PIT_EXT,
        client=object(),
        codes=["000001.SZ"],
        start_date="20240401",
        end_date="20240430",
        cache=False,
    )

    assert captured["date_field"] == "公布日"
    assert captured["as_of_date"] == "20240430"
    assert out.loc[0, "trade_date"].isoformat() == "2024-04-20"


def test_fetch_dataset_report_period_filters_report_date_not_announcement_date(monkeypatch):
    captured = {}

    def fake_query_infotable(client, table_id, **kwargs):
        captured.update(kwargs)
        return pd.DataFrame(
            {
                "StockID": ["SZ000001"],
                "截止日": ["20231231"],
                "公布日": ["20240420"],
                "每股收益(摊薄)": [1.2],
            }
        )

    monkeypatch.setattr(specs_module, "query_infotable", fake_query_infotable)

    fetch_dataset(
        STOCK_FINA_PIT_EXT,
        client=object(),
        codes=["000001.SZ"],
        report_period="20231231",
        cache=False,
    )

    assert captured["date_field"] == "截止日"
    assert captured["start_date"] == "20231231"
    assert captured["end_date"] == "20231231"
    assert captured["as_of_date"] is None


def test_fetch_dataset_report_period_accepts_explicit_as_of_date(monkeypatch):
    captured = {}

    def fake_query_infotable(client, table_id, **kwargs):
        captured.update(kwargs)
        return pd.DataFrame(
            {
                "StockID": ["SZ000001"],
                "截止日": ["20231231"],
                "公布日": ["20240420"],
                "每股收益(摊薄)": [1.2],
            }
        )

    monkeypatch.setattr(specs_module, "query_infotable", fake_query_infotable)

    fetch_dataset(
        STOCK_FINA_PIT_EXT,
        client=object(),
        codes=["000001.SZ"],
        report_period="20231231",
        as_of_date="20240430",
        cache=False,
    )

    assert captured["date_field"] == "截止日"
    assert captured["start_date"] == "20231231"
    assert captured["end_date"] == "20231231"
    assert captured["as_of_date"] == "20240430"


def test_fetch_dataset_preserves_explicit_unknown_fields(monkeypatch):
    def fake_query_infotable(client, table_id, **kwargs):
        return pd.DataFrame(
            {
                "StockID": ["OF012345"],
                "代码": ["OF000001"],
                "未登记字段": ["keep-me"],
            }
        )

    monkeypatch.setattr(specs_module, "query_infotable", fake_query_infotable)

    out = fetch_dataset(
        FUND_FOF_HOLDING_DETAIL,
        client=object(),
        codes=["012345.OF"],
        report_period="20231231",
        fields=["代码", "未登记字段"],
        cache=False,
    )

    assert out.loc[0, "holding_code_raw"] == "OF000001"
    assert out.loc[0, "未登记字段"] == "keep-me"


def test_fetch_dataset_passes_parallel_options_to_query_infotable(monkeypatch):
    captured = {}

    def fake_query_infotable(client, table_id, **kwargs):
        captured.update(kwargs)
        return pd.DataFrame(
            {
                "StockID": ["SZ000001"],
                "截止日": ["20231231"],
                "公布日": ["20240420"],
                "每股收益(摊薄)": [1.2],
            }
        )

    monkeypatch.setattr(specs_module, "query_infotable", fake_query_infotable)

    out = fetch_dataset(
        STOCK_FINA_PIT_EXT,
        client=object(),
        codes=["000001.SZ"],
        report_period="20231231",
        max_workers=4,
        progress=True,
        cache=False,
    )

    assert captured["options"].max_workers == 4
    assert captured["options"].progress is True
    assert out.loc[0, "trade_date"].isoformat() == "2024-04-20"


def test_fetch_dataset_includes_identifier_when_projecting_fields(monkeypatch):
    captured = {}

    def fake_query_infotable(client, table_id, **kwargs):
        captured["table_id"] = table_id
        captured.update(kwargs)
        return pd.DataFrame({"StockID": ["SZ000001"], "股票种类": ["A股"]})

    monkeypatch.setattr(specs_module, "query_infotable", fake_query_infotable)

    out = fetch_dataset(
        STOCK_IPO,
        codes=["000001.SZ"],
        fields=["stock_type"],
        cache=False,
    )

    assert captured["fields"] == ("StockID", "股票种类")
    assert list(out[["ts_code", "stock_type"]].iloc[0]) == ["000001.SZ", "A股"]
    assert "StockID" not in out.columns


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


def test_stock_margin_adds_tushare_compatible_fields_and_exchange_id():
    raw = pd.DataFrame(
        {
            "StockID": ["RZRQ000001", "RZRQ000002", "RZRQ000003"],
            "截止日": [20260728, 20260728, 20260728],
            "融资买入额": [1, 2, 3],
            "融资偿还额": [4, 5, 6],
            "融资余额": [7, 8, 9],
            "融券卖出量": [10, 11, 12],
            "融券偿还量": [13, 14, 15],
            "融券余量": [16, 17, 18],
            "融券余额": [19, 20, 21],
            "融资融券余额": [26, 28, 30],
        }
    )

    out = process_dataset_frame(raw, STOCK_MARGIN)

    assert out["exchange_id"].tolist() == ["SSE", "SZSE", "BSE"]
    assert out["tsl_code"].tolist() == ["RZRQ000001", "RZRQ000002", "RZRQ000003"]
    assert out["trade_date"].astype(str).tolist() == ["2026-07-28"] * 3
    assert out["rzmre"].tolist() == [1, 2, 3]
    assert out["rqchl"].tolist() == [13, 14, 15]
    assert out["margin_buy_amount"].tolist() == out["rzmre"].tolist()
    assert out["margin_short_balance"].tolist() == out["rzrqye"].tolist()


def test_stock_margindetail_adds_tushare_compatible_fields():
    raw = pd.DataFrame(
        {
            "StockID": ["SH600000"],
            "截止日": [20260728],
            "融资买入额": ["100.25"],
            "融资偿还额": ["80.25"],
            "融资余额": ["1000.00"],
            "融券卖出量": ["50"],
            "融券偿还量": ["20"],
            "融券余量": ["100"],
            "融券余额": ["500.00"],
            "融资融券余额": ["1500.00"],
        }
    )

    out = process_dataset_frame(raw, STOCK_MARGINDETAIL)

    assert out.loc[0, "ts_code"] == "600000.SH"
    assert out.loc[0, "tsl_code"] == "SH600000"
    assert out.loc[0, "rzrqye"] == pytest.approx(1500.0)
    assert out.loc[0, "rqchl"] == pytest.approx(20.0)
    assert out.loc[0, "margin_short_balance"] == out.loc[0, "rzrqye"]


def test_stock_margin_tushare_field_alias_projects_source_field(monkeypatch):
    captured = {}

    def fake_query_infotable(client, table_id, **kwargs):
        captured.update(kwargs)
        return pd.DataFrame(
            {
                "StockID": ["RZRQ000001"],
                "融资余额": ["1000.00"],
            }
        )

    monkeypatch.setattr(specs_module, "query_infotable", fake_query_infotable)

    out = fetch_dataset(
        STOCK_MARGIN,
        client=object(),
        trade_date="20260728",
        fields=["rzye"],
        cache=False,
    )

    assert captured["fields"] == ("StockID", "融资余额")
    assert out.loc[0, "rzye"] == pytest.approx(1000.0)
    assert out.loc[0, "margin_balance"] == out.loc[0, "rzye"]


def test_process_stock_valuation_indicator_spec():
    raw = pd.DataFrame(
        {
            "StockID": ["SZ000001"],
            "截止日": ["20231231"],
            "ROIC": ["3.99578"],
            "EV/IC": ["1.23"],
        }
    )

    out = process_dataset_frame(raw, STOCK_VALUATION_INDICATOR)

    assert out.loc[0, "tsl_code"] == "SZ000001"
    assert out.loc[0, "ts_code"] == "000001.SZ"
    assert out.loc[0, "report_date"].isoformat() == "2023-12-31"
    assert float(out.loc[0, "roic_pct"]) == 3.99578
    assert float(out.loc[0, "ev_to_ic"]) == 1.23
    assert out.loc[0, "source_table_name"] == "股票.估值指标"


def test_stock_valuation_indicator_executes_reportofall_array(monkeypatch):
    captured = {}

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            captured["tsl"] = tsl
            captured["as_dataframe"] = as_dataframe
            return [3.99578, -13.24497]

    monkeypatch.setattr(stock_module, "TinyClient", lambda: _Client())

    out = stock_module.stock_valuation_indicator(
        codes=["000001.SZ"],
        report_period="20231231",
        fields=["ROIC", "rotc_pct"],
        cache=False,
    )

    assert "setsysparam(pn_stock(),'SZ000001')" in captured["tsl"]
    assert "ReportOfAll(9901115,20231231)" in captured["tsl"]
    assert "ReportOfAll(9901123,20231231)" in captured["tsl"]
    assert captured["as_dataframe"] is False
    assert list(out[["ts_code", "roic_pct", "rotc_pct"]].iloc[0]) == ["000001.SZ", 3.99578, -13.24497]
    assert "ev" not in out.columns


def test_stock_valuation_indicator_batches_codes_in_one_tsl(monkeypatch):
    calls = []

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            calls.append((tsl, as_dataframe))
            return pd.DataFrame(
                {
                    "StockID": ["SZ000001", "SH600000"],
                    "截止日": ["20231231", "20231231"],
                    "ROIC": [3.99578, 4.25],
                    "有形资本回报率(%)": [-13.24497, 8.12],
                }
            )

    monkeypatch.setattr(stock_module, "TinyClient", lambda: _Client())

    out = stock_module.stock_valuation_indicator(
        codes=["000001.SZ", "600000.SH"],
        report_period="20231231",
        fields=["ROIC", "rotc_pct"],
        cache=False,
        progress=False,
    )

    assert len(calls) == 1
    tsl, as_dataframe = calls[0]
    assert as_dataframe is True
    assert "stocks:=array('SZ000001','SH600000')" in tsl
    assert "setsysparam(pn_stock(),stocks[i])" in tsl
    assert "ReportOfAll(9901115,20231231)" in tsl
    assert "ReportOfAll(9901123,20231231)" in tsl
    assert "array('StockID','截止日','ROIC','有形资本回报率(%)')" in tsl
    assert list(out["ts_code"]) == ["000001.SZ", "600000.SH"]
    assert list(out["roic_pct"].astype(float)) == [3.99578, 4.25]


def test_stock_valuation_indicator_code_batch_size_one_keeps_single_code_tsl(monkeypatch):
    calls = []

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            calls.append((tsl, as_dataframe))
            return [3.99578 if "SZ000001" in tsl else 4.25]

    monkeypatch.setattr(stock_module, "TinyClient", lambda: _Client())

    out = stock_module.stock_valuation_indicator(
        codes=["000001.SZ", "600000.SH"],
        report_period="20231231",
        fields=["roic_pct"],
        code_batch_size=1,
        cache=False,
        progress=False,
    )

    assert len(calls) == 2
    assert all(as_dataframe is False for _, as_dataframe in calls)
    assert all("stocks:=array" not in tsl for tsl, _ in calls)
    assert "setsysparam(pn_stock(),'SZ000001')" in calls[0][0]
    assert "setsysparam(pn_stock(),'SH600000')" in calls[1][0]
    assert list(out["ts_code"]) == ["000001.SZ", "600000.SH"]


def test_stock_valuation_indicator_batch_failure_falls_back_to_single_code_tsl(monkeypatch):
    calls = []

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            calls.append(tsl)
            if "stocks:=array" in tsl:
                raise RuntimeError("batch rejected")
            return [3.99578 if "SZ000001" in tsl else 4.25]

    monkeypatch.setattr(stock_module, "TinyClient", lambda: _Client())

    out = stock_module.stock_valuation_indicator(
        codes=["000001.SZ", "600000.SH"],
        report_period="20231231",
        fields=["roic_pct"],
        code_batch_size=20,
        cache=False,
        progress=False,
    )

    assert len(calls) == 3
    assert "stocks:=array('SZ000001','SH600000')" in calls[0]
    assert "setsysparam(pn_stock(),'SZ000001')" in calls[1]
    assert "setsysparam(pn_stock(),'SH600000')" in calls[2]
    assert list(out["ts_code"]) == ["000001.SZ", "600000.SH"]
    assert list(out["roic_pct"].astype(float)) == [3.99578, 4.25]


def test_stock_valuation_indicator_batch_empty_identifier_falls_back_to_single_code_tsl(monkeypatch):
    calls = []

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            calls.append(tsl)
            if "stocks:=array" in tsl:
                return pd.DataFrame({"StockID": ["", None], "ROIC": [99, 88]})
            return [3.99578 if "SZ000001" in tsl else 4.25]

    monkeypatch.setattr(stock_module, "TinyClient", lambda: _Client())

    out = stock_module.stock_valuation_indicator(
        codes=["000001.SZ", "600000.SH"],
        report_period="20231231",
        fields=["roic_pct"],
        code_batch_size=20,
        cache=False,
        progress=False,
    )

    assert len(calls) == 3
    assert "stocks:=array('SZ000001','SH600000')" in calls[0]
    assert "setsysparam(pn_stock(),'SZ000001')" in calls[1]
    assert "setsysparam(pn_stock(),'SH600000')" in calls[2]
    assert list(out["ts_code"]) == ["000001.SZ", "600000.SH"]
    assert list(out["roic_pct"].astype(float)) == [3.99578, 4.25]


def test_stock_valuation_indicator_accepts_string_field(monkeypatch):
    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            return [3.99578]

    monkeypatch.setattr(stock_module, "TinyClient", lambda: _Client())

    out = stock_module.stock_valuation_indicator(
        codes=["000001.SZ"],
        report_period="20231231",
        fields="roic_pct",
        cache=False,
    )

    assert list(out.columns) == [
        "tsl_code",
        "report_date",
        "roic_pct",
        "request_code",
        "ts_code",
        "source_table_id",
        "source_table_name",
    ]
    assert float(out.loc[0, "roic_pct"]) == 3.99578


def test_stock_valuation_indicator_requires_codes_and_report_period():
    with pytest.raises(TinyDataParameterError, match="requires report_period"):
        stock_module.stock_valuation_indicator(codes=["000001.SZ"], cache=False)
    with pytest.raises(TinyDataParameterError, match="requires one or more stock codes"):
        stock_module.stock_valuation_indicator(report_period="20231231", cache=False)
    with pytest.raises(TinyDataParameterError, match="Unknown"):
        stock_module.stock_valuation_indicator(codes=["000001.SZ"], report_period="20231231", fields=["not_a_metric"], cache=False)
    with pytest.raises(TinyDataParameterError, match="code_batch_size"):
        stock_module.stock_valuation_indicator(
            codes=["000001.SZ"],
            report_period="20231231",
            code_batch_size=0,
            cache=False,
        )


def test_process_stock_ttm_indicator_spec():
    raw = pd.DataFrame(
        {
            "StockID": ["SZ000001"],
            "截止日": ["20230930"],
            "取数日": ["20231031"],
            "营业总收入": ["105580000000"],
            "归属于母公司所有者净利润": ["39620000000"],
            "经营活动产生的现金流量净额": ["2500000000"],
        }
    )

    out = process_dataset_frame(raw, stock_module.STOCK_TTM_INDICATOR)

    assert out.loc[0, "tsl_code"] == "SZ000001"
    assert out.loc[0, "ts_code"] == "000001.SZ"
    assert out.loc[0, "report_date"].isoformat() == "2023-09-30"
    assert out.loc[0, "as_of_date"].isoformat() == "2023-10-31"
    assert float(out.loc[0, "total_revenue_ttm"]) == 105580000000
    assert float(out.loc[0, "parent_net_profit_ttm"]) == 39620000000
    assert float(out.loc[0, "net_operating_cashflow_ttm"]) == 2500000000
    assert out.loc[0, "source_table_name"] == "股票.TTM财务指标"


def test_stock_ttm_indicator_executes_last12mdata_array(monkeypatch):
    captured = {}

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            captured["tsl"] = tsl
            captured["as_dataframe"] = as_dataframe
            return [105580000000, 39620000000]

    monkeypatch.setattr(stock_module, "TinyClient", lambda: _Client())

    out = stock_module.stock_ttm_indicator(
        codes=["000001.SZ"],
        report_period="20230930",
        as_of_date="20231031",
        fields=["total_revenue_ttm", "parent_net_profit"],
        cache=False,
    )

    assert "setsysparam(pn_stock(),'SZ000001')" in captured["tsl"]
    assert "setsysparam(pn_date(),20231031T)" in captured["tsl"]
    assert "Last12MData(20230930,46080)" in captured["tsl"]
    assert "Last12MData(20230930,46078)" in captured["tsl"]
    assert captured["as_dataframe"] is False
    assert list(out[["ts_code", "total_revenue_ttm", "parent_net_profit_ttm"]].iloc[0]) == [
        "000001.SZ",
        105580000000,
        39620000000,
    ]
    assert "net_operating_cashflow_ttm" not in out.columns


def test_stock_ttm_indicator_batches_codes_in_one_tsl(monkeypatch):
    calls = []

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            calls.append((tsl, as_dataframe))
            return pd.DataFrame(
                {
                    "StockID": ["SZ000001", "SH600000"],
                    "截止日": ["20230930", "20230930"],
                    "取数日": ["20231031", "20231031"],
                    "营业总收入": [105580000000, 88990000000],
                    "归属于母公司所有者净利润": [39620000000, 28110000000],
                }
            )

    monkeypatch.setattr(stock_module, "TinyClient", lambda: _Client())

    out = stock_module.stock_ttm_indicator(
        codes=["000001.SZ", "600000.SH"],
        report_period="20230930",
        as_of_date="20231031",
        fields=["total_revenue_ttm", "parent_net_profit"],
        cache=False,
        progress=False,
    )

    assert len(calls) == 1
    tsl, as_dataframe = calls[0]
    assert as_dataframe is True
    assert "setsysparam(pn_date(),20231031T)" in tsl
    assert "stocks:=array('SZ000001','SH600000')" in tsl
    assert "setsysparam(pn_stock(),stocks[i])" in tsl
    assert "Last12MData(20230930,46080)" in tsl
    assert "Last12MData(20230930,46078)" in tsl
    assert "array('StockID','截止日','取数日','营业总收入','归属于母公司所有者净利润')" in tsl
    assert list(out["ts_code"]) == ["000001.SZ", "600000.SH"]
    assert list(out["parent_net_profit_ttm"].astype(float)) == [39620000000, 28110000000]


def test_stock_ttm_indicator_code_batch_size_one_keeps_single_code_tsl(monkeypatch):
    calls = []

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            calls.append((tsl, as_dataframe))
            return [105580000000 if "SZ000001" in tsl else 88990000000]

    monkeypatch.setattr(stock_module, "TinyClient", lambda: _Client())

    out = stock_module.stock_ttm_indicator(
        codes=["000001.SZ", "600000.SH"],
        report_period="20230930",
        fields=["total_revenue_ttm"],
        code_batch_size=1,
        cache=False,
        progress=False,
    )

    assert len(calls) == 2
    assert all(as_dataframe is False for _, as_dataframe in calls)
    assert all("stocks:=array" not in tsl for tsl, _ in calls)
    assert "setsysparam(pn_stock(),'SZ000001')" in calls[0][0]
    assert "setsysparam(pn_stock(),'SH600000')" in calls[1][0]
    assert list(out["ts_code"]) == ["000001.SZ", "600000.SH"]


def test_stock_ttm_indicator_batch_without_identifier_falls_back_to_single_code_tsl(monkeypatch):
    calls = []

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            calls.append(tsl)
            if "stocks:=array" in tsl:
                return pd.DataFrame({"营业总收入": [105580000000, 88990000000]})
            return [105580000000 if "SZ000001" in tsl else 88990000000]

    monkeypatch.setattr(stock_module, "TinyClient", lambda: _Client())

    out = stock_module.stock_ttm_indicator(
        codes=["000001.SZ", "600000.SH"],
        report_period="20230930",
        fields=["total_revenue_ttm"],
        code_batch_size=20,
        cache=False,
        progress=False,
    )

    assert len(calls) == 3
    assert "stocks:=array('SZ000001','SH600000')" in calls[0]
    assert "setsysparam(pn_stock(),'SZ000001')" in calls[1]
    assert "setsysparam(pn_stock(),'SH600000')" in calls[2]
    assert list(out["ts_code"]) == ["000001.SZ", "600000.SH"]
    assert list(out["total_revenue_ttm"].astype(float)) == [105580000000, 88990000000]


def test_stock_ttm_indicator_accepts_string_field(monkeypatch):
    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            return [2500000000]

    monkeypatch.setattr(stock_module, "TinyClient", lambda: _Client())

    out = stock_module.stock_ttm_indicator(
        codes=["000001.SZ"],
        report_period="20230930",
        fields="net_operating_cashflow_ttm",
        cache=False,
    )

    assert list(out.columns) == [
        "tsl_code",
        "report_date",
        "as_of_date",
        "net_operating_cashflow_ttm",
        "request_code",
        "ts_code",
        "source_table_id",
        "source_table_name",
    ]
    assert float(out.loc[0, "net_operating_cashflow_ttm"]) == 2500000000


def test_stock_ttm_indicator_requires_codes_report_period_and_whitelist():
    with pytest.raises(TinyDataParameterError, match="requires report_period"):
        stock_module.stock_ttm_indicator(codes=["000001.SZ"], cache=False)
    with pytest.raises(TinyDataParameterError, match="requires one or more stock codes"):
        stock_module.stock_ttm_indicator(report_period="20230930", cache=False)
    with pytest.raises(TinyDataParameterError, match="balance-sheet point-in-time items"):
        stock_module.stock_ttm_indicator(
            codes=["000001.SZ"],
            report_period="20230930",
            fields=["total_assets"],
            cache=False,
        )
    with pytest.raises(TinyDataParameterError, match="code_batch_size"):
        stock_module.stock_ttm_indicator(
            codes=["000001.SZ"],
            report_period="20230930",
            code_batch_size=0,
            cache=False,
        )


def test_process_new_reference_dataset_specs():
    fund_raw = pd.DataFrame(
        {
            "StockID": ["OF004905"],
            "截止日": ["20231231"],
            "公布日": ["20240330"],
            "资产总计": ["1000.5"],
            "负债合计": ["20"],
            "单位资产净值": ["1.2345"],
        }
    )
    stock_raw = pd.DataFrame(
        {
            "StockID": ["SZ000001"],
            "上市日": ["19910403"],
            "发行价": ["40.00"],
            "募集资金净额": ["1200"],
        }
    )
    trade_time_raw = pd.DataFrame(
        {
            "StockID": ["SH000001"],
            "截止日": ["20030721"],
            "竞价性质": ["上午连续竞价"],
            "开始时间": ["09:30:00"],
            "截止时间": ["11:30:00"],
            "序号": ["2"],
        }
    )

    fund_out = process_dataset_frame(fund_raw, FUND_BALANCE_SHEET)
    stock_out = process_dataset_frame(stock_raw, STOCK_IPO)
    time_out = process_dataset_frame(trade_time_raw, STOCK_TRADE_TIME)

    assert fund_out.loc[0, "report_date"].isoformat() == "2023-12-31"
    assert float(fund_out.loc[0, "total_assets"]) == 1000.5
    assert stock_out.loc[0, "list_date"].isoformat() == "1991-04-03"
    assert float(stock_out.loc[0, "issue_price"]) == 40.0
    assert time_out.loc[0, "market_code"] == "SH000001"
    assert int(time_out.loc[0, "seq_no"]) == 2


def test_fetch_fund_report_dataset_maps_share_code_to_main_code(monkeypatch):
    captured = {}

    def fake_query_infotable(client, table_id, **kwargs):
        captured.setdefault("calls", []).append((table_id, kwargs))
        if table_id == 302:
            return pd.DataFrame(
                {
                    "StockID": ["OF010031"],
                    "不同收费模式基金主代码": ["OF004905"],
                    "母基金代码": [0],
                }
            )
        assert table_id == 312
        assert kwargs["codes"] == ["OF004905"]
        return pd.DataFrame(
            {
                "StockID": ["OF004905"],
                "截止日": ["20231231"],
                "公布日": ["20240330"],
                "资产总计": [100],
            }
        )

    monkeypatch.setattr(specs_module, "query_infotable", fake_query_infotable)

    out = fetch_dataset(
        FUND_BALANCE_SHEET,
        client=object(),
        codes=["010031.OF"],
        report_period="20231231",
        cache=False,
    )

    assert [call[0] for call in captured["calls"]] == [302, 312]
    assert out.loc[0, "tsl_code"] == "OF004905"
    assert out.loc[0, "total_assets"] == 100


def test_process_fund_etf_constituent_spec():
    raw = pd.DataFrame(
        {
            "StockID": ["OF510050"],
            "截止日": ["20190816"],
            "代码": ["SH600000"],
            "名称": ["浦发银行"],
            "数量": ["5500"],
            "现金替代标志": ["允许"],
        }
    )

    out = process_dataset_frame(raw, FUND_ETF_CONSTITUENT)

    assert out.loc[0, "trade_date"].isoformat() == "2019-08-16"
    assert out.loc[0, "component_code_raw"] == "SH600000"
    assert float(out.loc[0, "quantity"]) == 5500.0


def test_fund_etf_constituent_batches_codes_in_one_tsl(monkeypatch):
    calls = []

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            calls.append((tsl, as_dataframe))
            return pd.DataFrame(
                {
                    "StockID": ["OF510050", "OF159915"],
                    "截止日": ["20190816", "20190816"],
                    "代码": ["SH600000", "SZ000001"],
                    "名称": ["浦发银行", "平安银行"],
                    "数量": ["5500", "600"],
                }
            )

    monkeypatch.setattr(fund_module, "TinyClient", lambda: _Client())

    out = fund_module.fund_etf_constituent(
        codes=["510050.OF", "159915.OF"],
        trade_date="20190816",
        cache=False,
        progress=False,
    )

    assert len(calls) == 1
    tsl, as_dataframe = calls[0]
    assert as_dataframe is True
    assert "stocks:=array('OF510050','OF159915')" in tsl
    assert "Ret:=GetFundETFConstituent(stocks[i],20190816T,tmp)" in tsl
    assert "tmp[:,'StockID']:=stocks[i]" in tsl
    assert "t&=select ['StockID'],* from tmp end" in tsl
    assert list(out["ts_code"]) == ["510050.OF", "159915.OF"]
    assert list(out["component_code_raw"]) == ["SH600000", "SZ000001"]
    assert list(out["quantity"].astype(float)) == [5500.0, 600.0]


def test_fund_etf_constituent_code_batch_size_one_keeps_single_code_tsl(monkeypatch):
    calls = []

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            calls.append(tsl)
            component = "SH600000" if "OF510050" in tsl else "SZ000001"
            return pd.DataFrame({"截止日": ["20190816"], "代码": [component], "数量": ["100"]})

    monkeypatch.setattr(fund_module, "TinyClient", lambda: _Client())

    out = fund_module.fund_etf_constituent(
        codes=["510050.OF", "159915.OF"],
        trade_date="20190816",
        code_batch_size=1,
        cache=False,
        progress=False,
    )

    assert len(calls) == 2
    assert all("stocks:=array" not in tsl for tsl in calls)
    assert "GetFundETFConstituent('OF510050',20190816T,t)" in calls[0]
    assert "GetFundETFConstituent('OF159915',20190816T,t)" in calls[1]
    assert list(out["ts_code"]) == ["510050.OF", "159915.OF"]
    assert list(out["component_code_raw"]) == ["SH600000", "SZ000001"]


def test_fund_etf_constituent_batch_failure_falls_back_to_single_code_tsl(monkeypatch):
    calls = []

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            calls.append(tsl)
            if "stocks:=array" in tsl:
                raise RuntimeError("batch rejected")
            component = "SH600000" if "OF510050" in tsl else "SZ000001"
            return pd.DataFrame({"截止日": ["20190816"], "代码": [component], "数量": ["100"]})

    monkeypatch.setattr(fund_module, "TinyClient", lambda: _Client())

    out = fund_module.fund_etf_constituent(
        codes=["510050.OF", "159915.OF"],
        trade_date="20190816",
        code_batch_size=20,
        cache=False,
        progress=False,
    )

    assert len(calls) == 3
    assert "stocks:=array('OF510050','OF159915')" in calls[0]
    assert "GetFundETFConstituent('OF510050',20190816T,t)" in calls[1]
    assert "GetFundETFConstituent('OF159915',20190816T,t)" in calls[2]
    assert list(out["ts_code"]) == ["510050.OF", "159915.OF"]
    assert list(out["component_code_raw"]) == ["SH600000", "SZ000001"]


def test_fund_etf_constituent_batch_missing_identifier_falls_back_to_single_code_tsl(monkeypatch):
    calls = []

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            calls.append(tsl)
            if "stocks:=array" in tsl:
                return pd.DataFrame({"截止日": ["20190816"], "代码": ["SH600000"], "数量": ["999"]})
            component = "SH600000" if "OF510050" in tsl else "SZ000001"
            return pd.DataFrame({"截止日": ["20190816"], "代码": [component], "数量": ["100"]})

    monkeypatch.setattr(fund_module, "TinyClient", lambda: _Client())

    out = fund_module.fund_etf_constituent(
        codes=["510050.OF", "159915.OF"],
        trade_date="20190816",
        code_batch_size=20,
        cache=False,
        progress=False,
    )

    assert len(calls) == 3
    assert "stocks:=array('OF510050','OF159915')" in calls[0]
    assert "GetFundETFConstituent('OF510050',20190816T,t)" in calls[1]
    assert "GetFundETFConstituent('OF159915',20190816T,t)" in calls[2]
    assert list(out["ts_code"]) == ["510050.OF", "159915.OF"]
    assert list(out["quantity"].astype(float)) == [100.0, 100.0]


def test_fund_etf_constituent_rejects_invalid_code_batch_size():
    with pytest.raises(TinyDataParameterError, match="code_batch_size"):
        fund_module.fund_etf_constituent(
            codes=["510050.OF"],
            trade_date="20190816",
            code_batch_size=0,
            cache=False,
        )


def test_process_index_weight_spec():
    raw = pd.DataFrame(
        {
            "StockID": ["SH000300"],
            "代码": ["SH600519"],
            "名称": ["贵州茅台"],
            "权重(%)": ["5.32"],
            "截止日": ["20210531"],
        }
    )

    out = process_dataset_frame(raw, INDEX_WEIGHT)

    assert out.loc[0, "index_code_raw"] == "SH000300"
    assert out.loc[0, "con_code_raw"] == "SH600519"
    assert float(out.loc[0, "weight_pct"]) == 5.32
    assert out.loc[0, "trade_date"].isoformat() == "2021-05-31"
    assert out.loc[0, "con_ts_code"] == "600519.SH"


def test_index_weight_batches_codes_in_one_tsl(monkeypatch):
    calls = []

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            calls.append((tsl, as_dataframe))
            return pd.DataFrame(
                {
                    "StockID": ["CSI000300", "CSI000905"],
                    "代码": ["SH600519", "SZ000001"],
                    "权重(%)": ["5.32", "1.23"],
                    "截止日": ["20210531", "20210531"],
                }
            )

    monkeypatch.setattr(index_module, "TinyClient", lambda: _Client())

    out = index_module.index_weight(
        codes=["000300.CSI", "000905.CSI"],
        trade_date="20210531",
        cache=False,
        progress=False,
    )

    assert len(calls) == 1
    tsl, as_dataframe = calls[0]
    assert as_dataframe is True
    assert "stocks:=array('CSI000300','CSI000905')" in tsl
    assert "GetBkWeightByDate(stocks[i],20210531T,tmp)" in tsl
    assert "tmp[:,'StockID']:=stocks[i]" in tsl
    assert "t&=select ['StockID'],* from tmp end" in tsl
    assert list(out["index_ts_code"]) == ["000300.CSI", "000905.CSI"]
    assert list(out["con_ts_code"]) == ["600519.SH", "000001.SZ"]
    assert list(out["weight_pct"].astype(float)) == [5.32, 1.23]


def test_index_weight_code_batch_size_one_keeps_single_code_tsl(monkeypatch):
    calls = []

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            calls.append(tsl)
            weight = "5.32" if "CSI000300" in tsl else "1.23"
            code = "SH600519" if "CSI000300" in tsl else "SZ000001"
            return pd.DataFrame({"代码": [code], "权重(%)": [weight]})

    monkeypatch.setattr(index_module, "TinyClient", lambda: _Client())

    out = index_module.index_weight(
        codes=["000300.CSI", "000905.CSI"],
        trade_date="20210531",
        code_batch_size=1,
        cache=False,
        progress=False,
    )

    assert len(calls) == 2
    assert all("stocks:=array" not in tsl for tsl in calls)
    assert "GetBkWeightByDate('CSI000300',20210531T,t)" in calls[0]
    assert "GetBkWeightByDate('CSI000905',20210531T,t)" in calls[1]
    assert list(out["index_ts_code"]) == ["000300.CSI", "000905.CSI"]
    assert list(out["weight_pct"].astype(float)) == [5.32, 1.23]


def test_index_weight_batch_failure_falls_back_to_single_code_tsl(monkeypatch):
    calls = []

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            calls.append(tsl)
            if "stocks:=array" in tsl:
                raise RuntimeError("batch rejected")
            weight = "5.32" if "CSI000300" in tsl else "1.23"
            code = "SH600519" if "CSI000300" in tsl else "SZ000001"
            return pd.DataFrame({"代码": [code], "权重(%)": [weight]})

    monkeypatch.setattr(index_module, "TinyClient", lambda: _Client())

    out = index_module.index_weight(
        codes=["000300.CSI", "000905.CSI"],
        trade_date="20210531",
        code_batch_size=20,
        cache=False,
        progress=False,
    )

    assert len(calls) == 3
    assert "stocks:=array('CSI000300','CSI000905')" in calls[0]
    assert "GetBkWeightByDate('CSI000300',20210531T,t)" in calls[1]
    assert "GetBkWeightByDate('CSI000905',20210531T,t)" in calls[2]
    assert list(out["index_ts_code"]) == ["000300.CSI", "000905.CSI"]
    assert list(out["weight_pct"].astype(float)) == [5.32, 1.23]


def test_index_weight_batch_empty_identifier_falls_back_to_single_code_tsl(monkeypatch):
    calls = []

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            calls.append(tsl)
            if "stocks:=array" in tsl:
                return pd.DataFrame({"StockID": ["", None], "代码": ["SH600000", "SZ000001"], "权重(%)": ["99", "88"]})
            weight = "5.32" if "CSI000300" in tsl else "1.23"
            code = "SH600519" if "CSI000300" in tsl else "SZ000001"
            return pd.DataFrame({"代码": [code], "权重(%)": [weight]})

    monkeypatch.setattr(index_module, "TinyClient", lambda: _Client())

    out = index_module.index_weight(
        codes=["000300.CSI", "000905.CSI"],
        trade_date="20210531",
        code_batch_size=20,
        cache=False,
        progress=False,
    )

    assert len(calls) == 3
    assert "stocks:=array('CSI000300','CSI000905')" in calls[0]
    assert "GetBkWeightByDate('CSI000300',20210531T,t)" in calls[1]
    assert "GetBkWeightByDate('CSI000905',20210531T,t)" in calls[2]
    assert list(out["index_ts_code"]) == ["000300.CSI", "000905.CSI"]
    assert list(out["weight_pct"].astype(float)) == [5.32, 1.23]


def test_index_weight_rejects_invalid_code_batch_size():
    with pytest.raises(TinyDataParameterError, match="code_batch_size"):
        index_module.index_weight(
            codes=["000300.CSI"],
            trade_date="20210531",
            code_batch_size=0,
            cache=False,
        )


def test_process_index_member_snapshot_spec():
    raw = pd.DataFrame(
        {
            "StockID": ["SH000300", "SH000300"],
            "代码": ["SH600519", "SZ000001"],
            "截止日": ["20210107", "20210107"],
        }
    )

    out = process_dataset_frame(raw, INDEX_MEMBER_SNAPSHOT)

    assert list(out["con_ts_code"]) == ["600519.SH", "000001.SZ"]
    assert out.loc[0, "trade_date"].isoformat() == "2021-01-07"
    assert (out["index_code_raw"] == "SH000300").all()


def test_process_index_valuation_spec():
    raw = pd.DataFrame(
        {
            "StockID": ["CSI000300"],
            "截止日": ["20231231"],
            "ROIC(加权平均,全部)": ["6.12"],
            "EV/IC(中位数,剔除亏损)": ["1.23"],
            "ROIC(TTM,中位数,剔除亏损)": ["7.89"],
        }
    )

    out = process_dataset_frame(raw, INDEX_VALUATION)

    assert out.loc[0, "index_code_raw"] == "CSI000300"
    assert out.loc[0, "index_ts_code"] == "000300.CSI"
    assert out.loc[0, "report_date"].isoformat() == "2023-12-31"
    assert float(out.loc[0, "roic_pct_weighted_all"]) == 6.12
    assert float(out.loc[0, "ev_to_ic_median_ex_loss"]) == 1.23
    assert float(out.loc[0, "roic_pct_ttm_median_ex_loss"]) == 7.89
    assert out.loc[0, "source_table_id"] == 762
    assert out.loc[0, "source_table_name"] == "指数.估值指标"


def test_index_valuation_field_ids_are_projected_as_source_names(monkeypatch):
    captured = {}

    def fake_query_infotable(client, table_id, **kwargs):
        captured.update(kwargs)
        assert table_id == 762
        return pd.DataFrame(
            {
                "StockID": ["CSI000300"],
                "截止日": ["20231231"],
                "ROIC(加权平均,全部)": [6.12],
                "EV/IC(中位数,剔除亏损)": [1.23],
            }
        )

    monkeypatch.setattr(specs_module, "query_infotable", fake_query_infotable)

    out = index_module.index_valuation(
        codes=["000300.CSI"],
        report_period="20231231",
        fields=["762034", "ev_to_ic_median_ex_loss"],
        cache=False,
    )

    assert captured["codes"] == ["CSI000300"]
    assert captured["date_field"] == "截止日"
    assert captured["start_date"] == "20231231"
    assert captured["end_date"] == "20231231"
    assert captured["fields"] == (
        "StockID",
        "截止日",
        "EV/IC(中位数,剔除亏损)",
        "ROIC(加权平均,全部)",
    )
    assert list(out[["index_ts_code", "roic_pct_weighted_all", "ev_to_ic_median_ex_loss"]].iloc[0]) == [
        "000300.CSI",
        6.12,
        1.23,
    ]


def test_index_valuation_rejects_unknown_fields():
    with pytest.raises(TinyDataParameterError, match="Unknown"):
        index_module.index_valuation(codes=["000300.CSI"], report_period="20231231", fields=["not_a_metric"], cache=False)


def test_process_fund_adjusted_nav_spec():
    raw = pd.DataFrame(
        {
            "StockID": ["OF510050"],
            "截止日": ["20190425"],
            "单位净值": ["2.345"],
            "复权净值": ["2.512"],
            "复权净值增长率(%)": ["7.12"],
        }
    )

    out = process_dataset_frame(raw, FUND_ADJUSTED_NAV)

    assert out.loc[0, "tsl_code"] == "OF510050"
    assert out.loc[0, "ts_code"] == "510050.OF"
    assert float(out.loc[0, "adjusted_nav"]) == 2.512
    assert float(out.loc[0, "unit_nav"]) == 2.345
    assert float(out.loc[0, "adjusted_return_pct"]) == 7.12


def test_fund_adjusted_nav_batches_codes_in_one_tsl(monkeypatch):
    calls = []

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            calls.append((tsl, as_dataframe))
            return pd.DataFrame(
                {
                    "StockID": ["OF510050", "OF159915"],
                    "截止日": ["20190425", "20190425"],
                    "单位净值": ["2.345", "1.234"],
                    "复权净值": ["2.512", "1.456"],
                }
            )

    monkeypatch.setattr(fund_module, "TinyClient", lambda: _Client())

    out = fund_module.fund_adjusted_nav(
        codes=["510050.OF", "159915.OF"],
        start_date="20190101",
        end_date="20190425",
        cache=False,
        progress=False,
    )

    assert len(calls) == 1
    tsl, as_dataframe = calls[0]
    assert as_dataframe is True
    assert "stocks:=array('OF510050','OF159915')" in tsl
    assert "tmp[:,'StockID']:=stocks[i]" in tsl
    assert "t&=select ['StockID'],* from tmp end" in tsl
    assert list(out["ts_code"]) == ["510050.OF", "159915.OF"]
    assert list(out["adjusted_nav"].astype(float)) == [2.512, 1.456]


def test_fund_adjusted_nav_code_batch_size_one_keeps_single_code_tsl(monkeypatch):
    calls = []

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            calls.append(tsl)
            return pd.DataFrame({"截止日": ["20190425"], "复权净值": ["2.512"]})

    monkeypatch.setattr(fund_module, "TinyClient", lambda: _Client())

    out = fund_module.fund_adjusted_nav(
        codes=["510050.OF", "159915.OF"],
        start_date="20190101",
        end_date="20190425",
        code_batch_size=1,
        cache=False,
        progress=False,
    )

    assert len(calls) == 2
    assert all("stocks:=array" not in tsl for tsl in calls)
    assert "setsysparam(pn_stock(),'OF510050')" in calls[0]
    assert "setsysparam(pn_stock(),'OF159915')" in calls[1]
    assert list(out["ts_code"]) == ["510050.OF", "159915.OF"]


def test_fund_adjusted_nav_batch_failure_falls_back_to_single_code_tsl(monkeypatch):
    calls = []

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            calls.append(tsl)
            if "stocks:=array" in tsl:
                raise RuntimeError("batch rejected")
            value = "2.512" if "OF510050" in tsl else "1.456"
            return pd.DataFrame({"截止日": ["20190425"], "复权净值": [value]})

    monkeypatch.setattr(fund_module, "TinyClient", lambda: _Client())

    out = fund_module.fund_adjusted_nav(
        codes=["510050.OF", "159915.OF"],
        start_date="20190101",
        end_date="20190425",
        code_batch_size=20,
        cache=False,
        progress=False,
    )

    assert len(calls) == 3
    assert "stocks:=array('OF510050','OF159915')" in calls[0]
    assert "setsysparam(pn_stock(),'OF510050')" in calls[1]
    assert "setsysparam(pn_stock(),'OF159915')" in calls[2]
    assert list(out["ts_code"]) == ["510050.OF", "159915.OF"]
    assert list(out["adjusted_nav"].astype(float)) == [2.512, 1.456]


def test_fund_adjusted_nav_batch_empty_identifier_falls_back_to_single_code_tsl(monkeypatch):
    calls = []

    class _Client:
        def exec(self, tsl, *, as_dataframe=False):
            calls.append(tsl)
            if "stocks:=array" in tsl:
                return pd.DataFrame({"StockID": ["", None], "截止日": ["20190425", "20190425"], "复权净值": ["99", "88"]})
            value = "2.512" if "OF510050" in tsl else "1.456"
            return pd.DataFrame({"截止日": ["20190425"], "复权净值": [value]})

    monkeypatch.setattr(fund_module, "TinyClient", lambda: _Client())

    out = fund_module.fund_adjusted_nav(
        codes=["510050.OF", "159915.OF"],
        start_date="20190101",
        end_date="20190425",
        code_batch_size=20,
        cache=False,
        progress=False,
    )

    assert len(calls) == 3
    assert "stocks:=array('OF510050','OF159915')" in calls[0]
    assert "setsysparam(pn_stock(),'OF510050')" in calls[1]
    assert "setsysparam(pn_stock(),'OF159915')" in calls[2]
    assert list(out["ts_code"]) == ["510050.OF", "159915.OF"]
    assert list(out["adjusted_nav"].astype(float)) == [2.512, 1.456]


def test_fund_adjusted_nav_rejects_invalid_code_batch_size():
    with pytest.raises(TinyDataParameterError, match="code_batch_size"):
        fund_module.fund_adjusted_nav(
            codes=["510050.OF"],
            start_date="20190101",
            end_date="20190425",
            code_batch_size=0,
            cache=False,
        )


def test_process_future_and_option_specs_normalize_contract_codes():
    future_raw = pd.DataFrame(
        {
            "StockID": ["IF2406.CFX"],
            "合约代码": ["IF2406.CFX"],
            "上市地": ["中国金融期货交易所"],
        }
    )
    option_raw = pd.DataFrame(
        {
            "StockID": ["10000001.SH"],
            "合约交易代码": ["10000001.SH"],
            "标的证券代码": ["SH510050"],
            "上市地": ["上海证券交易所"],
            "截止日": ["20240517"],
        }
    )

    future_out = process_dataset_frame(future_raw, FUTURE_BASIC_EXT)
    option_out = process_dataset_frame(option_raw, OPTION_BASIC_DAILY_EXT)

    assert future_out.loc[0, "contract_code_raw"] == "IF2406"
    assert future_out.loc[0, "ts_code"] == "IF2406.CFX"
    assert option_out.loc[0, "contract_code_raw"] == "10000001"
    assert option_out.loc[0, "ts_code"] == "10000001.SH"
    assert option_out.loc[0, "underlying_ts_code"] == "510050.SH"


def test_process_future_main_info_spec():
    raw = pd.DataFrame(
        {
            "StockID": ["ZLIF10"],
            "调整日期": ["20240520"],
            "调出日期": ["20240621"],
            "名称": ["沪深300股指期货"],
            "主力代码": ["IF2406"],
            "主力月份": ["2406"],
        }
    )

    out = process_dataset_frame(raw, FUTURE_MAIN_INFO)

    assert out.loc[0, "source_code"] == "ZLIF10"
    assert out.loc[0, "product_code"] == "ZLIF10"
    assert out.loc[0, "change_date"].isoformat() == "2024-05-20"
    assert out.loc[0, "out_date"].isoformat() == "2024-06-21"
    assert out.loc[0, "main_contract_code"] == "IF2406"
    assert int(out.loc[0, "main_contract_month"]) == 2406
    assert out.loc[0, "source_table_id"] == 700


def test_process_future_trade_ranking_spec():
    raw = pd.DataFrame(
        {
            "StockID": ["IF2406"],
            "代码": ["IF2406"],
            "截止日": ["20240520"],
            "排名类型": ["持买单量排名"],
            "排名": ["1"],
            "机构简称（标准化前）": ["中信期货"],
            "数量": ["12345"],
            "比上交易日增减": ["-67"],
            "机构简称": ["中信期货"],
        }
    )

    out = process_dataset_frame(raw, FUTURE_TRADE_RANKING)

    assert out.loc[0, "contract_code_raw"] == "IF2406"
    assert out.loc[0, "trade_date"].isoformat() == "2024-05-20"
    assert out.loc[0, "ranking_type"] == "持买单量排名"
    assert int(out.loc[0, "rank_no"]) == 1
    assert float(out.loc[0, "quantity"]) == 12345
    assert float(out.loc[0, "change_from_previous"]) == -67
    assert out.loc[0, "member_name"] == "中信期货"


def test_future_trade_ranking_filters_type_and_projects_fields(monkeypatch):
    captured = {}

    def fake_query_infotable(client, table_id, **kwargs):
        captured["table_id"] = table_id
        captured.update(kwargs)
        return pd.DataFrame(
            {
                "StockID": ["IF2406", "IF2406"],
                "代码": ["IF2406", "IF2406"],
                "截止日": ["20240520", "20240520"],
                "排名类型": ["持买单量排名", "持卖单量排名"],
                "排名": [1, 1],
                "数量": [12345, 23456],
                "机构简称": ["中信期货", "国泰君安"],
            }
        )

    monkeypatch.setattr(specs_module, "query_infotable", fake_query_infotable)

    out = future_module.future_trade_ranking(
        codes=["IF2406"],
        trade_date="20240520",
        ranking_type="long",
        fields=["排名", "数量", "机构简称"],
        cache=False,
    )

    assert captured["table_id"] == 701
    assert captured["codes"] == ["IF2406"]
    assert captured["date_field"] == "截止日"
    assert captured["fields"] == ("StockID", "代码", "截止日", "排名类型", "排名", "数量", "机构简称")
    assert list(out["ranking_type"]) == ["持买单量排名"]
    assert list(out["ranking_side"]) == ["long"]
    assert float(out.loc[0, "quantity"]) == 12345


def test_future_trade_ranking_rejects_unknown_ranking_type():
    with pytest.raises(TinyDataParameterError, match="ranking_type"):
        future_module.future_trade_ranking(codes=["IF2406"], trade_date="20240520", ranking_type="unknown", cache=False)

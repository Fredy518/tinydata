from __future__ import annotations

import pandas as pd

from tinydata.datasets.fund import FUND_ADJUSTED_NAV, FUND_BALANCE_SHEET, FUND_ETF_CONSTITUENT, FUND_FOF_HOLDING_DETAIL
from tinydata.datasets.index import INDEX_MEMBER_SNAPSHOT, INDEX_WEIGHT
from tinydata.datasets.stock import STOCK_FINA_PIT_EXT, STOCK_IPO, STOCK_TRADE_TIME
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

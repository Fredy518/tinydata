"""Index and market-calendar dataset APIs."""

from __future__ import annotations

from .specs import DatasetSpec, dataset_api, register_dataset


MARKET_CALENDAR_MULTI = register_dataset(
    DatasetSpec(
        name="market_calendar_multi",
        domain="calendar",
        priority="P0",
        table_id=753,
        source_table_name="指数.市场交易日历",
        date_field="截止日",
        code_kind="market",
        code_pool="market",
        code_batch_size=5,
        safe_query_required=True,
        postprocess="market_calendar",
        field_mapping={
            "截止日": "trade_date",
            "是否交易日": "is_trade_day",
            "交易日类别": "trade_day_type",
            "备注": "remark",
        },
        date_columns=("trade_date",),
        extra_columns=("market_code", "market_name"),
    )
)

TRADE_CALENDAR = register_dataset(
    DatasetSpec(
        name="trade_calendar",
        domain="calendar",
        priority="P0",
        table_id=753,
        source_table_name="指数.市场交易日历",
        date_field="截止日",
        code_kind="market",
        code_pool="market",
        code_batch_size=5,
        safe_query_required=True,
        postprocess="market_calendar",
        field_mapping={
            "截止日": "trade_date",
            "是否交易日": "is_trade_day",
            "交易日类别": "trade_day_type",
            "备注": "remark",
        },
        date_columns=("trade_date",),
        extra_columns=("market_code", "market_name"),
    )
)

INDEX_MEMBER_VERSIONED = register_dataset(
    DatasetSpec(
        name="index_member_versioned",
        domain="index",
        priority="P0",
        table_id=752,
        source_table_name="指数.指数成份",
        code_kind="index",
        code_pool="index",
        code_batch_size=500,
        safe_query_required=False,
        postprocess="index",
        field_mapping={
            "StockID": "index_code_raw",
            "stockid": "index_code_raw",
            "证券代码": "con_code_raw",
            "代码": "con_code_raw",
            "入选日期": "in_date",
            "剔除日期": "out_date",
            "成份标志": "member_flag",
            "入选公布日": "in_ann_date",
            "剔除公布日": "out_ann_date",
            "入选调整类型": "in_adjust_type",
            "剔除调整类型": "out_adjust_type",
        },
        date_columns=("in_date", "out_date", "in_ann_date", "out_ann_date", "latest_change_date"),
        numeric_columns=("member_flag",),
        integer_columns=("member_flag",),
        extra_columns=("index_ts_code", "con_ts_code", "latest_change_date"),
    )
)

INDEX_BASIC_EXT = register_dataset(
    DatasetSpec(
        name="index_basic_ext",
        domain="index",
        priority="P0",
        table_id=750,
        source_table_name="指数.指数基本信息",
        code_kind="index",
        code_pool="index",
        code_batch_size=500,
        safe_query_required=False,
        postprocess="index",
        field_mapping={
            "StockID": "index_code_raw",
            "stockid": "index_code_raw",
            "证券代码": "index_code_raw",
            "指数代码": "index_code_raw",
            "指数简称": "short_name",
            "指数全称": "full_name",
            "指数类型": "index_type",
            "指数标的": "index_target",
            "指数所属公司": "publisher",
            "开始日期": "start_date",
            "成立日期": "found_date",
            "指数起始点数": "base_point",
            "加权方式": "weighting_method",
            "样本个数": "sample_count",
            "样本调整周期": "sample_adjust_frequency",
            "备注": "remark",
            "停用日期": "stop_date",
            "指数一级分类": "category_l1",
            "指数二级分类": "category_l2",
            "指数三级分类": "category_l3",
            "指数四级分类": "category_l4",
            "指数主代码": "main_index_code_raw",
        },
        date_columns=("start_date", "found_date", "stop_date", "latest_change_date"),
        numeric_columns=("base_point", "sample_count"),
        integer_columns=("sample_count",),
        extra_columns=("index_ts_code", "latest_change_date"),
    )
)

market_calendar_multi = dataset_api(MARKET_CALENDAR_MULTI)
trade_calendar = dataset_api(TRADE_CALENDAR)
index_member_versioned = dataset_api(INDEX_MEMBER_VERSIONED)
index_basic_ext = dataset_api(INDEX_BASIC_EXT)

__all__ = [
    "INDEX_BASIC_EXT",
    "INDEX_MEMBER_VERSIONED",
    "MARKET_CALENDAR_MULTI",
    "TRADE_CALENDAR",
    "index_basic_ext",
    "index_member_versioned",
    "market_calendar_multi",
    "trade_calendar",
]

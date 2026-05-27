"""Index and market-calendar dataset APIs."""

from __future__ import annotations

import logging

import pandas as pd

from ..cache import CacheManager, make_cache_key
from ..client import TinyClient
from ..codes import normalize_codes
from ..errors import TinyDataParameterError
from ..infotable import format_tsl_datetime_literal, quote_tsl_string
from ..parallel import run_parallel_code_queries
from .specs import DatasetSpec, dataset_api, process_dataset_frame, register_dataset


logger = logging.getLogger(__name__)


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


INDEX_WEIGHT = register_dataset(
    DatasetSpec(
        name="index_weight",
        domain="index",
        priority="P1",
        table_id=0,
        source_table_name="GetBkWeightByDate",
        source_kind="tsl_function",
        code_kind="index",
        code_pool="index",
        code_batch_size=1,
        safe_query_required=True,
        postprocess="index",
        field_mapping={
            "StockID": "index_code_raw",
            "stockid": "index_code_raw",
            "代码": "con_code_raw",
            "证券代码": "con_code_raw",
            "名称": "con_name",
            "StockName": "con_name",
            "权重(%)": "weight_pct",
            "权重": "weight_pct",
            "比例(%)": "weight_pct",
            "截止日": "trade_date",
        },
        date_columns=("trade_date",),
        numeric_columns=("weight_pct",),
        extra_columns=("index_ts_code", "con_ts_code"),
    )
)


INDEX_MEMBER_SNAPSHOT = register_dataset(
    DatasetSpec(
        name="index_member_snapshot",
        domain="index",
        priority="P1",
        table_id=0,
        source_table_name="GetBKByDate",
        source_kind="tsl_function",
        code_kind="index",
        code_pool="index",
        code_batch_size=1,
        safe_query_required=True,
        postprocess="index",
        field_mapping={
            "StockID": "index_code_raw",
            "stockid": "index_code_raw",
            "代码": "con_code_raw",
            "截止日": "trade_date",
        },
        date_columns=("trade_date",),
        extra_columns=("index_ts_code", "con_ts_code", "extend_flag"),
    )
)


def _build_snapshot_cache_key(spec: DatasetSpec, codes: list[str], trade_date: object, extra: dict) -> str:
    payload = {"codes": codes, "trade_date": str(trade_date), "field_version": spec.field_version}
    payload.update({str(k): v for k, v in extra.items()})
    return make_cache_key(spec.name, payload)


def index_weight(
    codes=None,
    trade_date=None,
    *,
    refresh: bool = False,
    cache: bool = True,
    max_workers: int | None = None,
    progress: bool | None = None,
    max_codes=None,
) -> pd.DataFrame:
    """Fetch index constituent weights through Tinysoft ``GetBkWeightByDate``."""

    if trade_date in (None, ""):
        raise TinyDataParameterError("index_weight requires trade_date.")
    normalized = normalize_codes(codes, kind="index")
    if not normalized:
        raise TinyDataParameterError("index_weight requires one or more index codes.")
    if max_codes is not None:
        normalized = normalized[: max(1, int(max_codes))]

    manager = CacheManager()
    key = _build_snapshot_cache_key(INDEX_WEIGHT, normalized, trade_date, {})
    if cache and not refresh:
        cached = manager.read(INDEX_WEIGHT.name, key)
        if cached is not None:
            return cached

    date_literal = format_tsl_datetime_literal(trade_date)
    client = TinyClient()

    def fetch_one(code: str) -> pd.DataFrame | None:
        tsl = (
            f"Ret:=GetBkWeightByDate({quote_tsl_string(code)},{date_literal},t);"
            "If Ret then Return t; Else Return array();"
        )
        raw = client.exec(tsl, as_dataframe=True)
        if raw is None or raw.empty:
            return None
        raw = raw.copy()
        raw["StockID"] = code
        if "截止日" not in raw.columns:
            raw["截止日"] = trade_date
        return process_dataset_frame(raw, INDEX_WEIGHT)

    frames = [
        frame
        for frame in run_parallel_code_queries(
            normalized,
            fetch_one=fetch_one,
            max_workers=max_workers,
            progress=progress,
            description=f"{INDEX_WEIGHT.name} codes",
            logger=logger,
            rate_limit_scope=f"parallel {INDEX_WEIGHT.name} queries",
        )
        if not frame.empty
    ]

    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if cache:
        manager.write(INDEX_WEIGHT.name, key, out)
    return out


def index_member_snapshot(
    codes=None,
    trade_date=None,
    *,
    extend: bool = False,
    refresh: bool = False,
    cache: bool = True,
    max_workers: int | None = None,
    progress: bool | None = None,
    max_codes=None,
) -> pd.DataFrame:
    """Fetch indexed constituents on a specific date through ``GetBKByDate``.

    ``extend=True`` falls back to the weight table when the constituent table is
    empty (the Tinysoft ``ExType`` parameter).
    """

    if trade_date in (None, ""):
        raise TinyDataParameterError("index_member_snapshot requires trade_date.")
    normalized = normalize_codes(codes, kind="index")
    if not normalized:
        raise TinyDataParameterError("index_member_snapshot requires one or more index codes.")
    if max_codes is not None:
        normalized = normalized[: max(1, int(max_codes))]

    manager = CacheManager()
    key = _build_snapshot_cache_key(
        INDEX_MEMBER_SNAPSHOT,
        normalized,
        trade_date,
        {"extend": bool(extend)},
    )
    if cache and not refresh:
        cached = manager.read(INDEX_MEMBER_SNAPSHOT.name, key)
        if cached is not None:
            return cached

    date_literal = format_tsl_datetime_literal(trade_date)
    ex_type = 1 if extend else 0
    client = TinyClient()

    def fetch_one(code: str) -> pd.DataFrame | None:
        tsl = (
            f"stks:=GetBKByDate({quote_tsl_string(code)},{date_literal},{ex_type});Return stks;"
        )
        raw = client.exec(tsl, as_dataframe=False)
        members = _extract_string_array(raw)
        if not members:
            return None
        rows = [{"StockID": code, "代码": member, "截止日": trade_date} for member in members]
        raw_df = pd.DataFrame(rows)
        processed = process_dataset_frame(raw_df, INDEX_MEMBER_SNAPSHOT)
        processed["extend_flag"] = bool(extend)
        return processed

    frames = [
        frame
        for frame in run_parallel_code_queries(
            normalized,
            fetch_one=fetch_one,
            max_workers=max_workers,
            progress=progress,
            description=f"{INDEX_MEMBER_SNAPSHOT.name} codes",
            logger=logger,
            rate_limit_scope=f"parallel {INDEX_MEMBER_SNAPSHOT.name} queries",
        )
        if not frame.empty
    ]

    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if cache:
        manager.write(INDEX_MEMBER_SNAPSHOT.name, key, out)
    return out


def _extract_string_array(payload) -> list[str]:
    """Unwrap TS-OPI payloads that contain a flat string array."""

    if payload is None:
        return []
    if isinstance(payload, list):
        data = payload
    elif isinstance(payload, dict):
        for key in ("data", "Data", "value", "Value"):
            if key in payload and isinstance(payload[key], list):
                data = payload[key]
                break
        else:
            return []
    else:
        return []
    out: list[str] = []
    for item in data:
        if isinstance(item, str):
            text = item.strip()
            if text:
                out.append(text)
        elif isinstance(item, dict):
            for key in ("代码", "StockID", "stockid", "value"):
                if key in item:
                    text = str(item[key] or "").strip()
                    if text:
                        out.append(text)
                        break
    return out


__all__ = [
    "INDEX_BASIC_EXT",
    "INDEX_MEMBER_VERSIONED",
    "INDEX_MEMBER_SNAPSHOT",
    "INDEX_WEIGHT",
    "MARKET_CALENDAR_MULTI",
    "TRADE_CALENDAR",
    "index_basic_ext",
    "index_member_snapshot",
    "index_member_versioned",
    "index_weight",
    "market_calendar_multi",
    "trade_calendar",
]

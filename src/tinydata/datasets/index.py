"""Index and market-calendar dataset APIs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Sequence

import pandas as pd

from ..cache import CacheManager, make_cache_key
from ..client import TinyClient
from ..codes import normalize_codes, tinysoft_symbol_series_to_ts_code
from ..errors import TinyDataParameterError, TinyDataRateLimitError
from ..infotable import chunked, format_tsl_datetime_literal, quote_tsl_string
from ..parallel import run_parallel_code_queries
from .specs import DatasetSpec, dataset_api, fetch_dataset, process_dataset_frame, register_dataset


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


@dataclass(frozen=True)
class _IndexValuationMetric:
    field_id: int
    source_name: str
    column: str


def _index_valuation_block(
    start_id: int,
    display_name: str,
    column_base: str,
    *,
    period: str | None = None,
    base_weight_label: str = "加权平均",
) -> tuple[_IndexValuationMetric, ...]:
    prefix = f"{column_base}_{period.lower()}_" if period else f"{column_base}_"
    if period:
        return (
            _IndexValuationMetric(start_id, f"{display_name}({period},加权,全部)", f"{prefix}weighted_all"),
            _IndexValuationMetric(start_id + 1, f"{display_name}({period},加权,剔除亏损)", f"{prefix}weighted_ex_loss"),
            _IndexValuationMetric(start_id + 2, f"{display_name}({period},中位数,全部)", f"{prefix}median_all"),
            _IndexValuationMetric(start_id + 3, f"{display_name}({period},中位数,剔除亏损)", f"{prefix}median_ex_loss"),
        )
    return (
        _IndexValuationMetric(start_id, f"{display_name}({base_weight_label},全部)", f"{prefix}weighted_all"),
        _IndexValuationMetric(start_id + 1, f"{display_name}({base_weight_label},剔除亏损)", f"{prefix}weighted_ex_loss"),
        _IndexValuationMetric(start_id + 2, f"{display_name}(中位数,全部)", f"{prefix}median_all"),
        _IndexValuationMetric(start_id + 3, f"{display_name}(中位数,剔除亏损)", f"{prefix}median_ex_loss"),
    )


_INDEX_VALUATION_METRICS: tuple[_IndexValuationMetric, ...] = (
    *_index_valuation_block(762002, "每股自由现金流", "fcff_per_share", base_weight_label="加权"),
    *_index_valuation_block(762042, "每股自由现金流", "fcff_per_share", period="季度"),
    *_index_valuation_block(762046, "每股自由现金流", "fcff_per_share", period="TTM"),
    *_index_valuation_block(762006, "EBIT/营业收入", "ebit_to_revenue"),
    *_index_valuation_block(762050, "EBIT/营业收入", "ebit_to_revenue", period="季度"),
    *_index_valuation_block(762054, "EBIT/营业收入", "ebit_to_revenue", period="TTM"),
    *_index_valuation_block(762010, "EBITDA/营业收入", "ebitda_to_revenue"),
    *_index_valuation_block(762058, "EBITDA/营业收入", "ebitda_to_revenue", period="季度"),
    *_index_valuation_block(762062, "EBITDA/营业收入", "ebitda_to_revenue", period="TTM"),
    *_index_valuation_block(762014, "EV/营业收入", "ev_to_revenue"),
    *_index_valuation_block(762066, "EV/营业收入", "ev_to_revenue", period="季度"),
    *_index_valuation_block(762070, "EV/营业收入", "ev_to_revenue", period="TTM"),
    *_index_valuation_block(762018, "EV/EBIT", "ev_to_ebit"),
    *_index_valuation_block(762074, "EV/EBIT", "ev_to_ebit", period="季度"),
    *_index_valuation_block(762078, "EV/EBIT", "ev_to_ebit", period="TTM"),
    *_index_valuation_block(762022, "EV/EBITDA", "ev_to_ebitda"),
    *_index_valuation_block(762082, "EV/EBITDA", "ev_to_ebitda", period="季度"),
    *_index_valuation_block(762086, "EV/EBITDA", "ev_to_ebitda", period="TTM"),
    *_index_valuation_block(762026, "EV/NOPLAT", "ev_to_noplat"),
    *_index_valuation_block(762090, "EV/NOPLAT", "ev_to_noplat", period="季度"),
    *_index_valuation_block(762094, "EV/NOPLAT", "ev_to_noplat", period="TTM"),
    *_index_valuation_block(762030, "EV/IC", "ev_to_ic"),
    *_index_valuation_block(762098, "EV/IC", "ev_to_ic", period="季度"),
    *_index_valuation_block(762102, "EV/IC", "ev_to_ic", period="TTM"),
    *_index_valuation_block(762034, "ROIC", "roic_pct"),
    *_index_valuation_block(762106, "ROIC", "roic_pct", period="季度"),
    *_index_valuation_block(762110, "ROIC", "roic_pct", period="TTM"),
    *_index_valuation_block(762038, "有形资本回报率(%)", "rotc_pct"),
    *_index_valuation_block(762114, "有形资本回报率(%)", "rotc_pct", period="季度"),
    *_index_valuation_block(762118, "有形资本回报率(%)", "rotc_pct", period="TTM"),
)


_INDEX_VALUATION_IDENTIFIER_FIELDS = {
    "stockid",
    "证券代码",
    "指数代码",
    "index_code_raw",
    "index_ts_code",
    "request_code",
    "report_date",
    "截止日",
    "source_table_id",
    "source_table_name",
}


INDEX_VALUATION = register_dataset(
    DatasetSpec(
        name="index_valuation",
        domain="index",
        priority="P1",
        table_id=762,
        source_table_name="指数.估值指标",
        frequency="quarterly",
        date_field="截止日",
        code_kind="index",
        code_pool="index",
        code_batch_size=200,
        safe_query_required=True,
        postprocess="index",
        field_mapping={
            "StockID": "index_code_raw",
            "stockid": "index_code_raw",
            "证券代码": "index_code_raw",
            "指数代码": "index_code_raw",
            "截止日": "report_date",
            **{metric.source_name: metric.column for metric in _INDEX_VALUATION_METRICS},
        },
        date_columns=("report_date",),
        numeric_columns=tuple(metric.column for metric in _INDEX_VALUATION_METRICS),
        extra_columns=("index_ts_code",),
    )
)


def _normalize_index_valuation_fields(fields: Optional[Sequence[str]]) -> Optional[tuple[str, ...]]:
    if not fields:
        return None
    if isinstance(fields, (str, bytes)):
        fields = [str(fields)]

    aliases: dict[str, _IndexValuationMetric] = {}
    for metric in _INDEX_VALUATION_METRICS:
        aliases[metric.source_name.lower()] = metric
        aliases[metric.column.lower()] = metric
        aliases[str(metric.field_id)] = metric

    identifier_fields = {field.lower() for field in _INDEX_VALUATION_IDENTIFIER_FIELDS}
    selected: list[_IndexValuationMetric] = []
    seen: set[int] = set()
    unknown: list[str] = []
    for field in fields:
        text = str(field or "").strip()
        if not text or text.lower() in identifier_fields:
            continue
        metric = aliases.get(text.lower())
        if metric is None:
            unknown.append(text)
            continue
        if metric.field_id not in seen:
            selected.append(metric)
            seen.add(metric.field_id)

    if unknown:
        allowed = ", ".join(metric.column for metric in _INDEX_VALUATION_METRICS)
        raise TinyDataParameterError(
            "index_valuation fields must be valuation metric names, mapped columns, or InfoTable field ids. "
            f"Unknown: {unknown}. Allowed mapped columns: {allowed}."
        )
    if not selected:
        raise TinyDataParameterError("index_valuation fields must include at least one valuation metric.")
    return ("StockID", "截止日", *(metric.source_name for metric in selected))


market_calendar_multi = dataset_api(MARKET_CALENDAR_MULTI)
trade_calendar = dataset_api(TRADE_CALENDAR)
index_member_versioned = dataset_api(INDEX_MEMBER_VERSIONED)
index_basic_ext = dataset_api(INDEX_BASIC_EXT)


def index_valuation(
    codes=None,
    start_date=None,
    end_date=None,
    report_period=None,
    trade_date=None,
    refresh: bool = False,
    cache: bool = True,
    code_batch_size: int | None = None,
    max_workers: int | None = None,
    progress: bool | None = None,
    max_codes: int | None = None,
    fields: Optional[Sequence[str]] = None,
    all_history: bool = False,
    report_mode: int | None = None,
    as_of_date=None,
) -> pd.DataFrame:
    """Fetch index valuation indicators from Tinysoft InfoTable 762."""

    out = fetch_dataset(
        INDEX_VALUATION,
        codes=codes,
        start_date=start_date,
        end_date=end_date,
        report_period=report_period,
        trade_date=trade_date,
        refresh=refresh,
        cache=cache,
        code_batch_size=code_batch_size,
        max_workers=max_workers,
        progress=progress,
        max_codes=max_codes,
        fields=_normalize_index_valuation_fields(fields),
        all_history=all_history,
        report_mode=report_mode,
        as_of_date=as_of_date,
    )
    if fields and not out.empty and "index_ts_code" not in out.columns and "index_code_raw" in out.columns:
        out = out.copy()
        out["index_ts_code"] = tinysoft_symbol_series_to_ts_code(out["index_code_raw"])
    return out


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
        code_batch_size=20,
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


def _normalize_index_function_batch_size(code_batch_size: int | None, *, default: int) -> int:
    if code_batch_size is None:
        return max(1, int(default))
    size = int(code_batch_size)
    if size < 1:
        raise TinyDataParameterError("code_batch_size must be >= 1.")
    return size


def _has_index_code_identifier(raw: pd.DataFrame) -> bool:
    candidate_columns = [
        column
        for column in raw.columns
        if str(column).lower() in {"stockid", "tsl_code"} or column == "证券代码"
    ]
    for column in candidate_columns:
        values = raw[column]
        non_blank = values.notna() & values.astype("string").str.strip().ne("")
        if bool(non_blank.all()):
            return True
    return False


def _build_index_weight_single_tsl(code: str, *, date_literal: str) -> str:
    return (
        f"Ret:=GetBkWeightByDate({quote_tsl_string(code)},{date_literal},t);"
        "If Ret then Return t; Else Return array();"
    )


def _build_index_weight_batch_tsl(codes: list[str], *, date_literal: str) -> str:
    stocks_literal = "array(" + ",".join(quote_tsl_string(code) for code in codes) + ")"
    return (
        f"stocks:={stocks_literal};"
        "t:=array();"
        "for i:=0 to length(stocks)-1 do "
        "begin "
        f"Ret:=GetBkWeightByDate(stocks[i],{date_literal},tmp);"
        "if Ret then "
        "begin "
        "tmp[:,'StockID']:=stocks[i];"
        "t&=select ['StockID'],* from tmp end;"
        "end;"
        "end;"
        "return t;"
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
    code_batch_size: int | None = None,
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
    batch_size = _normalize_index_function_batch_size(code_batch_size, default=INDEX_WEIGHT.code_batch_size)

    manager = CacheManager()
    key = _build_snapshot_cache_key(INDEX_WEIGHT, normalized, trade_date, {"code_batch_size": batch_size})
    if cache and not refresh:
        cached = manager.read(INDEX_WEIGHT.name, key)
        if cached is not None:
            return cached

    date_literal = format_tsl_datetime_literal(trade_date)
    client = TinyClient()

    def fetch_one(code: str) -> pd.DataFrame | None:
        raw = client.exec(_build_index_weight_single_tsl(code, date_literal=date_literal), as_dataframe=True)
        if raw is None or raw.empty:
            return None
        raw = raw.copy()
        if not _has_index_code_identifier(raw):
            raw["StockID"] = code
        if "截止日" not in raw.columns:
            raw["截止日"] = trade_date
        return process_dataset_frame(raw, INDEX_WEIGHT)

    def fetch_batch(batch: list[str]) -> pd.DataFrame | None:
        if len(batch) == 1:
            return fetch_one(batch[0])
        try:
            raw = client.exec(_build_index_weight_batch_tsl(batch, date_literal=date_literal), as_dataframe=True)
            if raw is None or raw.empty:
                return None
            if _has_index_code_identifier(raw):
                raw = raw.copy()
                if "截止日" not in raw.columns:
                    raw["截止日"] = trade_date
                return process_dataset_frame(raw, INDEX_WEIGHT)
            logger.warning(
                "Tinysoft batched index_weight result has no code identifier; falling back to single-code requests."
            )
        except TinyDataRateLimitError:
            raise
        except Exception:
            logger.warning(
                "Tinysoft rejected batched index_weight request for %s code(s); falling back to single-code requests.",
                len(batch),
            )
        frames = [frame for code in batch if (frame := fetch_one(code)) is not None and not frame.empty]
        return pd.concat(frames, ignore_index=True) if frames else None

    if batch_size == 1 or len(normalized) == 1:
        tasks = normalized
        fetch_task = fetch_one
        description = f"{INDEX_WEIGHT.name} codes"
        rate_scope = f"parallel {INDEX_WEIGHT.name} queries"
    else:
        tasks = chunked(normalized, batch_size)
        fetch_task = fetch_batch
        description = f"{INDEX_WEIGHT.name} batches"
        rate_scope = f"parallel {INDEX_WEIGHT.name} batch queries"

    frames = [
        frame
        for frame in run_parallel_code_queries(
            tasks,
            fetch_one=fetch_task,
            max_workers=max_workers,
            progress=progress,
            description=description,
            logger=logger,
            rate_limit_scope=rate_scope,
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

    Multi-code batching is intentionally not exposed yet: ``GetBKByDate``
    returns a string array, and flattening per-index arrays into a tagged table
    depends on unverified Tinysoft array expansion semantics.
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
    "INDEX_VALUATION",
    "INDEX_WEIGHT",
    "MARKET_CALENDAR_MULTI",
    "TRADE_CALENDAR",
    "index_basic_ext",
    "index_member_snapshot",
    "index_member_versioned",
    "index_valuation",
    "index_weight",
    "market_calendar_multi",
    "trade_calendar",
]

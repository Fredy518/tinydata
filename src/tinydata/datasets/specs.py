"""Dataset metadata, registry helpers, and frame processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence

import pandas as pd

from ..cache import CacheManager, make_cache_key
from ..client import TinyClient
from ..codes import (
    normalize_codes,
    tinysoft_symbol_series_to_ts_code,
    tinysoft_symbol_to_ts_code,
    ts_code_series_to_tinysoft_symbol,
)
from ..errors import TinyDataCodePoolError, TinyDataParameterError, TinyDataQueryError
from ..infotable import InfoTableOptions, query_infotable
from ..universe import resolve_universe


Postprocessor = Callable[[pd.DataFrame, "DatasetSpec"], pd.DataFrame]


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    table_id: int
    source_table_name: str
    field_mapping: Dict[str, str]
    domain: str = "misc"
    priority: str = "P0"
    source_kind: str = "infotable"
    frequency: Optional[str] = None
    date_field: Optional[str] = None
    allow_full_table: bool = False
    code_kind: Optional[str] = None
    code_pool: Optional[str] = None
    code_batch_size: int = 100
    field_version: str = "v1"
    date_columns: Sequence[str] = field(default_factory=tuple)
    numeric_columns: Sequence[str] = field(default_factory=tuple)
    integer_columns: Sequence[str] = field(default_factory=tuple)
    safe_query_required: bool = False
    postprocess: Optional[str] = None
    extra_columns: Sequence[str] = field(default_factory=tuple)
    code_transform: Optional[str] = None

    def info(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "domain": self.domain,
            "priority": self.priority,
            "source_kind": self.source_kind,
            "table_id": self.table_id,
            "source_table_name": self.source_table_name,
            "frequency": self.frequency,
            "date_field": self.date_field,
            "allow_full_table": self.allow_full_table,
            "code_kind": self.code_kind,
            "code_batch_size": self.code_batch_size,
            "field_version": self.field_version,
            "safe_query_required": self.safe_query_required,
            "code_transform": self.code_transform,
            "fields": dict(self.field_mapping),
        }


_REGISTRY: dict[str, DatasetSpec] = {}


def register_dataset(spec: DatasetSpec) -> DatasetSpec:
    if spec.name in _REGISTRY:
        raise ValueError(f"Duplicate tinydata dataset name: {spec.name}")
    _REGISTRY[spec.name] = spec
    return spec


def get_dataset_spec(name: str) -> DatasetSpec:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"Unknown tinydata dataset: {name}") from exc


def list_dataset_specs(*, domain: Optional[str] = None, priority: Optional[str] = None) -> list[DatasetSpec]:
    specs = list(_REGISTRY.values())
    if domain:
        specs = [spec for spec in specs if spec.domain == domain]
    if priority:
        specs = [spec for spec in specs if spec.priority == priority]
    return sorted(specs, key=lambda spec: (spec.domain, spec.priority, spec.name))


def list_datasets(domain: Optional[str] = None, priority: Optional[str] = None) -> pd.DataFrame:
    rows = [spec.info() for spec in list_dataset_specs(domain=domain, priority=priority)]
    if not rows:
        return pd.DataFrame(columns=["name", "domain", "priority", "table_id", "source_table_name"])
    return pd.DataFrame(rows)


def get_dataset_info(name: str) -> dict[str, Any]:
    return get_dataset_spec(name).info()


def _parse_tinysoft_dates(values: pd.Series) -> pd.Series:
    if values.empty:
        return pd.to_datetime(values, errors="coerce")
    text = values.astype("string").str.strip()
    parsed = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    yyyymmdd_mask = text.str.fullmatch(r"\d{8}").fillna(False)
    if yyyymmdd_mask.any():
        parsed.loc[yyyymmdd_mask] = pd.to_datetime(
            text.loc[yyyymmdd_mask],
            format="%Y%m%d",
            errors="coerce",
        )
    remaining_mask = ~yyyymmdd_mask
    if remaining_mask.any():
        parsed.loc[remaining_mask] = pd.to_datetime(text.loc[remaining_mask], errors="coerce")
    return parsed


def _normalize_date_values(values: pd.Series) -> pd.Series:
    return _parse_tinysoft_dates(values).dt.date


def _normalize_dates(df: pd.DataFrame, columns: Sequence[str]) -> None:
    for col in columns:
        if col in df.columns:
            df[col] = _normalize_date_values(df[col])


def _normalize_numeric(df: pd.DataFrame, columns: Sequence[str]) -> None:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")


def _normalize_integer(df: pd.DataFrame, columns: Sequence[str]) -> None:
    for col in columns:
        if col in df.columns:
            values = pd.to_numeric(df[col], errors="coerce")
            df[col] = values.astype("Int64")


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    text = str(value).strip()
    if not text or text.lower() in {"none", "nan", "null"}:
        return None
    return text


def _clean_tinysoft_code(value: Any, *, kind: Optional[str] = None) -> Optional[str]:
    text = _clean_text(value)
    if text is None or text in {"0", "0.0"}:
        return None
    normalized = normalize_codes([text], kind=kind)
    return normalized[0] if normalized else None


def _normalize_tinysoft_codes(values: pd.Series, *, kind: Optional[str] = None) -> pd.Series:
    normalized = ts_code_series_to_tinysoft_symbol(values, kind=kind)
    return normalized.mask(normalized.isin({"0", "0.0"}))


def _normalize_upper_text(values: pd.Series) -> pd.Series:
    text = values.astype("string").str.strip()
    lowered = text.str.lower()
    text = text.mask((text == "") | lowered.isin({"none", "nan", "null"}))
    out = text.str.upper().astype("object")
    out.loc[text.isna()] = None
    return out


def _contract_ts_code_series(codes: pd.Series, exchange_names: pd.Series, mapping: Mapping[str, str]) -> pd.Series:
    code_text = _normalize_upper_text(codes).astype("string")
    exchange_text = exchange_names.astype("string").str.strip()
    suffix = exchange_text.map(mapping)
    out = pd.Series([None] * len(codes), index=codes.index, dtype="object")
    code_part = code_text.str.split(".", n=1).str[0]
    mask = code_part.notna() & suffix.notna()
    if mask.any():
        match_index = mask[mask].index
        out.loc[match_index] = (code_part.loc[match_index] + "." + suffix.loc[match_index]).astype("object")
    return out


def _northbound_channel_series(values: pd.Series) -> pd.Series:
    text = _normalize_upper_text(values).astype("string")
    out = pd.Series([None] * len(values), index=values.index, dtype="object")
    sh_mask = text.str.startswith("SH", na=False) | text.str.endswith(".SH", na=False) | text.str.startswith(("5", "6", "9"), na=False)
    sz_mask = text.str.startswith("SZ", na=False) | text.str.endswith(".SZ", na=False) | text.str.startswith(("0", "1", "2", "3"), na=False)
    if sh_mask.any():
        out.loc[sh_mask] = "HG000002"
    if sz_mask.any():
        out.loc[sz_mask] = "HG000004"
    return out


def _to_bool_series(values: pd.Series) -> pd.Series:
    text = values.astype("string").str.strip()
    lowered = text.str.lower()
    out = pd.Series([None] * len(values), index=values.index, dtype="object")
    true_mask = lowered.isin({"1", "true", "yes", "y"}) | text.isin(["是", "交易日"])
    false_mask = lowered.isin({"0", "false", "no", "n"}) | text.isin(["否", "非交易日", "休市"])
    if true_mask.any():
        out.loc[true_mask] = True
    if false_mask.any():
        out.loc[false_mask] = False
    return out


def _first_existing(df: pd.DataFrame, columns: Sequence[str]) -> Optional[pd.Series]:
    for col in columns:
        if col in df.columns:
            return df[col]
    return None


def _coalesce_columns(df: pd.DataFrame, target: str, candidates: Sequence[str]) -> None:
    if target in df.columns:
        base = df[target]
    else:
        base = pd.Series([None] * len(df), index=df.index)
    for col in candidates:
        if col in df.columns:
            base = base.where(base.notna() & (base.astype(str).str.strip() != ""), df[col])
    df[target] = base


def _northbound_channel(value: Any) -> Optional[str]:
    raw = str(value or "").strip().upper()
    if raw.startswith("SH") or raw.endswith(".SH") or raw.startswith(("5", "6", "9")):
        return "HG000002"
    if raw.startswith("SZ") or raw.endswith(".SZ") or raw.startswith(("0", "1", "2", "3")):
        return "HG000004"
    return None


_CHANNEL_NAMES = {
    "HG000001": "沪港通",
    "HG000002": "沪股通",
    "HG000003": "深港通",
    "HG000004": "深股通",
}


_MARKET_NAMES = {
    "SH000001": "A股市场",
    "SZ399001": "A股市场",
    "QI000001": "国内期货市场",
    "HKHSI001": "港股市场",
    "HSG000001": "南向交易日历",
    "HSG000002": "北向交易日历",
    "CBICBA00301": "银行间债券市场",
}


def _to_bool(value: Any) -> Optional[bool]:
    text = _clean_text(value)
    if text is None:
        return None
    lowered = text.lower()
    if lowered in {"1", "true", "yes", "y", "是", "交易日"}:
        return True
    if lowered in {"0", "false", "no", "n", "否", "非交易日", "休市"}:
        return False
    return None


def _index_ts_code(value: Any) -> Optional[str]:
    raw = _clean_text(value)
    if not raw:
        return None
    mapped = tinysoft_symbol_to_ts_code(raw)
    if mapped:
        return mapped
    text = raw.upper()
    if text.startswith(("CSI", "CNI")) and len(text) == 9:
        return f"{text[-6:]}.{text[:3]}"
    return None


_FUTURE_SUFFIX_BY_EXCHANGE = {
    "中国金融期货交易所": "CFX",
    "上海期货交易所": "SHF",
    "上海国际能源交易中心": "INE",
    "大连商品交易所": "DCE",
    "郑州商品交易所": "ZCE",
    "广州期货交易所": "GFE",
}


_OPTION_SUFFIX_BY_EXCHANGE = {
    "上海证券交易所": "SH",
    "深圳证券交易所": "SZ",
    "中国金融期货交易所": "CFX",
    **_FUTURE_SUFFIX_BY_EXCHANGE,
}


def _contract_ts_code(code: Any, exchange_name: Any, mapping: Mapping[str, str]) -> Optional[str]:
    raw = _clean_text(code)
    if not raw:
        return None
    text = raw.upper().split(".", 1)[0]
    suffix = mapping.get(str(exchange_name or "").strip())
    return f"{text}.{suffix}" if suffix else None


def _postprocess_hsgt_channel(df: pd.DataFrame, spec: DatasetSpec) -> pd.DataFrame:
    _coalesce_columns(df, "channel_code", ["request_code", "StockID", "stockid", "tsl_code"])
    df["channel_code"] = _normalize_upper_text(df["channel_code"])
    df["channel_name"] = df["channel_code"].map(_CHANNEL_NAMES)
    return df


def _postprocess_hsgt_stock(df: pd.DataFrame, spec: DatasetSpec) -> pd.DataFrame:
    _coalesce_columns(df, "security_code_raw", ["request_code", "StockID", "stockid", "tsl_code"])
    if "channel_code" not in df.columns:
        df["channel_code"] = _northbound_channel_series(df["security_code_raw"])
    df["channel_name"] = df["channel_code"].map(_CHANNEL_NAMES)
    if "ts_code" not in df.columns:
        df["ts_code"] = tinysoft_symbol_series_to_ts_code(df["security_code_raw"])
    return df


def _postprocess_market_calendar(df: pd.DataFrame, spec: DatasetSpec) -> pd.DataFrame:
    _coalesce_columns(df, "market_code", ["request_code", "StockID", "stockid", "证券代码"])
    df["market_code"] = _normalize_upper_text(df["market_code"])
    df["market_name"] = df["market_code"].map(_MARKET_NAMES)
    if "is_trade_day" in df.columns:
        df["is_trade_day"] = _to_bool_series(df["is_trade_day"])
    return df


def _postprocess_index(df: pd.DataFrame, spec: DatasetSpec) -> pd.DataFrame:
    _coalesce_columns(df, "index_code_raw", ["request_code", "StockID", "stockid", "证券代码", "指数代码"])
    df["index_code_raw"] = ts_code_series_to_tinysoft_symbol(df["index_code_raw"], kind="index")
    df["index_ts_code"] = df["index_code_raw"].map(_index_ts_code)
    if "con_code_raw" in df.columns:
        df["con_ts_code"] = tinysoft_symbol_series_to_ts_code(df["con_code_raw"])
    if {"in_date", "out_date", "in_ann_date", "out_ann_date"} & set(df.columns):
        dates = pd.DataFrame(
            {
                col: _parse_tinysoft_dates(df[col])
                for col in ("in_date", "out_date", "in_ann_date", "out_ann_date")
                if col in df.columns
            }
        )
        if not dates.empty:
            df["latest_change_date"] = dates.max(axis=1).dt.date
    return df


def _postprocess_bond(df: pd.DataFrame, spec: DatasetSpec) -> pd.DataFrame:
    _coalesce_columns(df, "bond_code_raw", ["request_code", "source_code", "StockID", "stockid"])
    df["bond_code_raw"] = df["bond_code_raw"].map(_clean_text)
    df["bond_ts_code"] = tinysoft_symbol_series_to_ts_code(df["bond_code_raw"])
    if "underlying_code_raw" in df.columns:
        df["underlying_ts_code"] = tinysoft_symbol_series_to_ts_code(df["underlying_code_raw"])
    return df


def _postprocess_future(df: pd.DataFrame, spec: DatasetSpec) -> pd.DataFrame:
    _coalesce_columns(df, "source_code", ["request_code", "StockID", "stockid"])
    _coalesce_columns(df, "contract_code_raw", ["source_code"])
    df["contract_code_raw"] = ts_code_series_to_tinysoft_symbol(df["contract_code_raw"], kind="future")
    if "product_code" in df.columns:
        df["product_code"] = _normalize_upper_text(df["product_code"])
    df["ts_code"] = _contract_ts_code_series(df["contract_code_raw"], df.get("exchange_name", pd.Series(index=df.index)), _FUTURE_SUFFIX_BY_EXCHANGE)
    return df


def _postprocess_future_product(df: pd.DataFrame, spec: DatasetSpec) -> pd.DataFrame:
    _coalesce_columns(df, "source_code", ["request_code", "StockID", "stockid"])
    _coalesce_columns(df, "product_code", ["source_code"])
    for col in df.columns:
        if col.endswith("_code") or col.endswith("_contract_code") or col in {"product_code", "source_code"}:
            df[col] = _normalize_upper_text(df[col])
    return df


def _postprocess_option(df: pd.DataFrame, spec: DatasetSpec) -> pd.DataFrame:
    _coalesce_columns(df, "source_code", ["request_code", "StockID", "stockid"])
    _coalesce_columns(df, "contract_code_raw", ["contract_trade_code", "source_code"])
    df["contract_code_raw"] = ts_code_series_to_tinysoft_symbol(df["contract_code_raw"], kind="option")
    df["ts_code"] = _contract_ts_code_series(df["contract_code_raw"], df.get("exchange_name", pd.Series(index=df.index)), _OPTION_SUFFIX_BY_EXCHANGE)
    if "underlying_code_raw" in df.columns:
        df["underlying_ts_code"] = tinysoft_symbol_series_to_ts_code(df["underlying_code_raw"])
    return df


def _postprocess_suspend(df: pd.DataFrame, spec: DatasetSpec) -> pd.DataFrame:
    if "suspend_start_date" in df.columns:
        df["trade_date"] = _normalize_date_values(df["suspend_start_date"])
    if "suspend_reason" in df.columns:
        df["event_text"] = df["suspend_reason"].map(_clean_text)
        df["event_type"] = df["event_text"].map(
            lambda x: "resume" if x and "复牌" in x else ("suspend" if x and ("停牌" in x or "临时停" in x) else "other")
        )
    return df


def _postprocess_industry(df: pd.DataFrame, spec: DatasetSpec) -> pd.DataFrame:
    _coalesce_columns(df, "tsl_code", ["request_code", "StockID", "stockid", "证券代码"])
    if "ts_code" not in df.columns:
        df["ts_code"] = tinysoft_symbol_series_to_ts_code(df["tsl_code"])
    if "in_date" in df.columns:
        df["trade_date"] = _normalize_date_values(df["in_date"])
    df["industry_source"] = df.get("root_attr_code", "unknown")
    df["source_name"] = df.get("root_attr_name", None)
    level = pd.to_numeric(df.get("level_no"), errors="coerce") if "level_no" in df.columns else None
    if level is not None:
        df["industry_l1"] = df["attr_name"].where(level == 1, None) if "attr_name" in df.columns else None
        df["industry_l2"] = df["attr_name"].where(level == 2, None) if "attr_name" in df.columns else None
        df["industry_l3"] = df["attr_name"].where(level == 3, None) if "attr_name" in df.columns else None
    if "attr_code" in df.columns:
        df["industry_code"] = df["attr_code"]
    return df


_FINA_METRICS = {
    "metric_eps_diluted": ("eps_diluted", 42002, "每股收益(摊薄)"),
    "metric_bps": ("bps", 42006, "每股净资产"),
    "metric_roe_diluted": ("roe_diluted", 42012, "净资产收益率(摊薄)(%)"),
    "metric_netprofit_excl_nr": ("netprofit_excl_nr", 42017, "扣除非经常性损益后的净利润"),
}

_FINA_METRIC_NAMES = {key: value[0] for key, value in _FINA_METRICS.items()}
_FINA_METRIC_FIELD_IDS = {key: value[1] for key, value in _FINA_METRICS.items()}
_FINA_METRIC_EXPRS = {key: value[2] for key, value in _FINA_METRICS.items()}


def _postprocess_fina_pit(df: pd.DataFrame, spec: DatasetSpec) -> pd.DataFrame:
    out = df.copy()
    if "ann_date" in out.columns:
        out["trade_date"] = _normalize_date_values(out["ann_date"])
    elif "report_date" in out.columns:
        out["trade_date"] = _normalize_date_values(out["report_date"])

    metric_cols = [col for col in _FINA_METRICS if col in out.columns]
    if not metric_cols:
        return out

    id_cols = ["ts_code", "tsl_code", "request_code", "trade_date", "report_date", "ann_date"]
    for col in id_cols:
        if col not in out.columns:
            out[col] = None

    long = out[id_cols + metric_cols].melt(
        id_vars=id_cols,
        value_vars=metric_cols,
        var_name="_metric_col",
        value_name="metric_value",
    )
    long = long[long["metric_value"].notna()].copy()
    if long.empty:
        return out

    long["finance_source"] = "report_42_main"
    long["metric_name"] = long["_metric_col"].map(_FINA_METRIC_NAMES)
    long["metric_field_id"] = long["_metric_col"].map(_FINA_METRIC_FIELD_IDS)
    long["metric_expr"] = long["_metric_col"].map(_FINA_METRIC_EXPRS)
    long["metric_text"] = long["metric_value"].map(str)
    return long[
        [
            "ts_code",
            "tsl_code",
            "request_code",
            "trade_date",
            "report_date",
            "ann_date",
            "finance_source",
            "metric_name",
            "metric_expr",
            "metric_field_id",
            "metric_value",
            "metric_text",
        ]
    ]


_POSTPROCESSORS: dict[str, Postprocessor] = {
    "hsgt_channel": _postprocess_hsgt_channel,
    "hsgt_stock": _postprocess_hsgt_stock,
    "market_calendar": _postprocess_market_calendar,
    "index": _postprocess_index,
    "bond": _postprocess_bond,
    "future": _postprocess_future,
    "future_product": _postprocess_future_product,
    "option": _postprocess_option,
    "stock_suspend": _postprocess_suspend,
    "stock_industry": _postprocess_industry,
    "stock_fina_pit": _postprocess_fina_pit,
}


def process_dataset_frame(
    df: pd.DataFrame,
    spec: DatasetSpec,
    *,
    preserve_columns: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    rename_map = {src: dst for src, dst in spec.field_mapping.items() if src in out.columns}
    if rename_map:
        out.rename(columns=rename_map, inplace=True)
        out = out.loc[:, ~out.columns.duplicated()]

    if "tsl_code" not in out.columns:
        source = _first_existing(out, ["StockID", "stockid", "证券代码", "request_code"])
        if source is not None:
            out["tsl_code"] = source

    if "request_code" not in out.columns:
        source = _first_existing(out, ["tsl_code", "source_code", "index_code_raw", "bond_code_raw", "contract_code_raw"])
        if source is not None:
            out["request_code"] = source

    if "ts_code" not in out.columns and "tsl_code" in out.columns:
        out["ts_code"] = tinysoft_symbol_series_to_ts_code(out["tsl_code"])

    _normalize_dates(out, spec.date_columns)
    _normalize_numeric(out, spec.numeric_columns)
    _normalize_integer(out, spec.integer_columns)

    if spec.postprocess:
        processor = _POSTPROCESSORS.get(spec.postprocess)
        if processor is not None:
            out = processor(out, spec)
            _normalize_dates(out, spec.date_columns)
            _normalize_numeric(out, spec.numeric_columns)
            _normalize_integer(out, spec.integer_columns)

    out["source_table_id"] = spec.table_id
    out["source_table_name"] = spec.source_table_name
    if "request_code" not in out.columns and "tsl_code" in out.columns:
        out["request_code"] = out["tsl_code"]

    allowed_columns = set(spec.field_mapping.values()) | set(spec.extra_columns) | {
        "ts_code",
        "tsl_code",
        "request_code",
        "source_table_id",
        "source_table_name",
    }
    if preserve_columns:
        allowed_columns.update(str(col).strip() for col in preserve_columns if str(col or "").strip())
    ordered_columns = [col for col in out.columns if col in allowed_columns]
    return out[ordered_columns]


def _dataset_query_fields(spec: DatasetSpec, fields: Optional[Sequence[str]] = None) -> Sequence[str]:
    selected = set(fields or [])
    out = []
    seen = set()
    for source, target in spec.field_mapping.items():
        if selected and source not in selected and target not in selected:
            continue
        text = str(source or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        out.append(text)
        seen.add(key)
    for field_name in fields or ():
        if field_name in spec.field_mapping.values():
            continue
        text = str(field_name or "").strip()
        key = text.lower()
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return tuple(out)


def _ensure_query_identifier_fields(spec: DatasetSpec, query_fields: Sequence[str]) -> Sequence[str]:
    seen = {str(field).lower() for field in query_fields}
    if "stockid" in seen or "证券代码" in seen:
        return tuple(query_fields)
    for source in ("StockID", "stockid", "证券代码"):
        if source in spec.field_mapping:
            return (source, *tuple(query_fields))
    return tuple(query_fields)


def _has_query_window(*, start_date: Any, end_date: Any, report_period: Any, trade_date: Any) -> bool:
    return any(value not in (None, "") for value in (start_date, end_date, report_period, trade_date))


def _resolve_codes(
    spec: DatasetSpec,
    *,
    client: Optional[TinyClient],
    codes: Optional[Iterable[Any]],
    start_date: Any,
    end_date: Any,
    trade_date: Any,
    refresh: bool,
    max_codes: Optional[int],
) -> list[str]:
    if codes is not None and not isinstance(codes, str):
        resolved = normalize_codes(codes, kind=spec.code_kind)
    elif isinstance(codes, str) and codes.strip():
        resolved = normalize_codes(codes, kind=spec.code_kind)
    else:
        resolved = []

    if not resolved and spec.code_kind:
        resolved = resolve_universe(
            spec.code_kind,
            refresh=refresh,
            start_date=start_date,
            end_date=end_date,
            trade_date=trade_date,
            client=client,
        )

    if max_codes is not None:
        resolved = resolved[: max(1, int(max_codes))]

    if resolved and spec.code_transform in {"fund_main_or_parent", "fund_parent_if_present"}:
        resolved = _transform_fund_codes(
            resolved,
            mode=spec.code_transform,
            client=client,
        )
    return resolved


def _transform_fund_codes(codes: Sequence[str], *, mode: str, client: Optional[TinyClient]) -> list[str]:
    """Map fund share codes to Tinysoft report-table access codes when documented."""

    if not codes:
        return []
    use_client = client or TinyClient()
    try:
        raw = query_infotable(
            use_client,
            302,
            codes=codes,
            fields=("StockID", "不同收费模式基金主代码", "母基金代码"),
            options=InfoTableOptions(
                code_batch_size=500,
                code_kind="fund",
                retries=2,
                fallback_to_single=True,
                skip_failed_codes=True,
            ),
        )
    except Exception:
        return list(dict.fromkeys(codes))

    mapping: dict[str, str] = {}
    if raw is not None and not raw.empty:
        if "StockID" in raw.columns:
            source_values = raw["StockID"]
        elif "stockid" in raw.columns:
            source_values = raw["stockid"]
        else:
            source_values = pd.Series([None] * len(raw), index=raw.index)
        source = _normalize_tinysoft_codes(source_values, kind="fund")
        parent = _normalize_tinysoft_codes(
            raw["母基金代码"] if "母基金代码" in raw.columns else pd.Series([None] * len(raw), index=raw.index),
            kind="fund",
        )
        main = _normalize_tinysoft_codes(
            raw["不同收费模式基金主代码"] if "不同收费模式基金主代码" in raw.columns else pd.Series([None] * len(raw), index=raw.index),
            kind="fund",
        )
        if mode == "fund_parent_if_present":
            target = parent.fillna(source)
        else:
            target = parent.fillna(main).fillna(source)
        valid = source.notna() & target.notna()
        mapping = dict(zip(source.loc[valid], target.loc[valid]))

    transformed = [mapping.get(code, code) for code in codes]
    return list(dict.fromkeys(transformed))


def fetch_dataset(
    spec: DatasetSpec,
    *,
    client: Optional[TinyClient] = None,
    codes: Optional[Iterable[Any]] = None,
    start_date: Any = None,
    end_date: Any = None,
    report_period: Any = None,
    trade_date: Any = None,
    refresh: bool = False,
    cache: bool = True,
    code_batch_size: Optional[int] = None,
    max_workers: Optional[int] = None,
    progress: Optional[bool] = None,
    max_codes: Optional[int] = None,
    fields: Optional[Sequence[str]] = None,
    all_history: bool = False,
    report_mode: Optional[int] = None,
    as_of_date: Any = None,
) -> pd.DataFrame:
    query_date_field = spec.date_field
    effective_as_of_date = as_of_date
    if spec.source_kind != "infotable":
        raise TinyDataParameterError(f"{spec.name} is a {spec.source_kind} dataset. Use its dedicated public API.")

    if report_period is not None:
        start_date = report_period
        end_date = report_period
        if "截止日" in spec.field_mapping:
            query_date_field = "截止日"
    if trade_date is not None:
        start_date = trade_date
        end_date = trade_date
        if effective_as_of_date is None:
            effective_as_of_date = trade_date
    elif report_period is None and effective_as_of_date is None:
        effective_as_of_date = end_date

    if spec.safe_query_required and not all_history and not _has_query_window(
        start_date=start_date, end_date=end_date, report_period=report_period, trade_date=trade_date
    ):
        raise TinyDataParameterError(
            f"{spec.name} is a high-volume dataset. Pass report_period/trade_date/start_date/end_date "
            "or set all_history=True explicitly."
        )

    query_codes: Optional[list[str]] = None
    explicit_codes = codes is not None and (not isinstance(codes, str) or bool(str(codes).strip()))
    if explicit_codes or not spec.allow_full_table:
        query_codes = _resolve_codes(
            spec,
            client=client,
            codes=codes,
            start_date=start_date,
            end_date=end_date,
            trade_date=trade_date,
            refresh=refresh,
            max_codes=max_codes,
        )
        if not query_codes and not spec.allow_full_table:
            raise TinyDataCodePoolError(f"Dataset {spec.name} requires codes but no valid code pool was available.")

    query_fields = _dataset_query_fields(spec, fields)
    if fields and query_codes:
        query_fields = _ensure_query_identifier_fields(spec, query_fields)

    cache_params = {
        "codes": query_codes,
        "start_date": start_date,
        "end_date": end_date,
        "report_period": report_period,
        "trade_date": trade_date,
        "table_id": spec.table_id,
        "field_version": spec.field_version,
        "fields": query_fields,
        "all_history": all_history,
        "code_batch_size": code_batch_size or spec.code_batch_size,
        "query_date_field": query_date_field,
        "as_of_date": effective_as_of_date,
        "report_mode": report_mode,
    }
    manager = CacheManager()
    key = make_cache_key(spec.name, cache_params)
    if cache and not refresh:
        cached = manager.read(spec.name, key)
        if cached is not None:
            return cached

    opts = InfoTableOptions(
        code_batch_size=code_batch_size or spec.code_batch_size,
        code_kind=spec.code_kind,
        max_workers=max_workers,
        progress=progress,
    )
    use_client = client or TinyClient()
    try:
        raw = query_infotable(
            use_client,
            spec.table_id,
            codes=query_codes,
            start_date=start_date,
            end_date=end_date,
            date_field=query_date_field,
            fields=query_fields,
            allow_full_table=spec.allow_full_table and not query_codes,
            as_of_date=effective_as_of_date,
            report_mode=report_mode,
            options=opts,
        )
    except TinyDataQueryError as exc:
        message = str(exc)
        if spec.allow_full_table and not query_codes and spec.code_kind and "requires codes" in message:
            query_codes = _resolve_codes(
                spec,
                client=use_client,
                codes=codes,
                start_date=start_date,
                end_date=end_date,
                trade_date=trade_date,
                refresh=refresh,
                max_codes=max_codes,
            )
            if not query_codes:
                raise TinyDataCodePoolError(f"Dataset {spec.name} requires codes but no valid code pool was available.") from exc
            raw = query_infotable(
                use_client,
                spec.table_id,
                codes=query_codes,
                start_date=start_date,
                end_date=end_date,
                date_field=query_date_field,
                fields=query_fields,
                allow_full_table=False,
                as_of_date=effective_as_of_date,
                report_mode=report_mode,
                options=opts,
            )
        else:
            raise

    processed = process_dataset_frame(raw, spec, preserve_columns=query_fields if fields else None)
    if fields:
        keep = {"source_table_id", "source_table_name", "request_code", "tsl_code", "ts_code"}
        for field_name in fields:
            text = str(field_name or "").strip()
            if not text:
                continue
            keep.add(text)
            keep.add(spec.field_mapping.get(text, text))
        processed = processed[[col for col in processed.columns if col in keep]]
    if cache:
        manager.write(spec.name, key, processed)
    return processed


def dataset_api(spec: DatasetSpec):
    def api(
        codes: Optional[Iterable[Any]] = None,
        start_date: Any = None,
        end_date: Any = None,
        report_period: Any = None,
        trade_date: Any = None,
        refresh: bool = False,
        cache: bool = True,
        code_batch_size: Optional[int] = None,
        max_workers: Optional[int] = None,
        progress: Optional[bool] = None,
        max_codes: Optional[int] = None,
        fields: Optional[Sequence[str]] = None,
        all_history: bool = False,
        report_mode: Optional[int] = None,
        as_of_date: Any = None,
    ) -> pd.DataFrame:
        return fetch_dataset(
            spec,
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
            fields=fields,
            all_history=all_history,
            report_mode=report_mode,
            as_of_date=as_of_date,
        )

    api.__name__ = spec.name
    api.__doc__ = f"Fetch Tinysoft dataset {spec.name} ({spec.source_table_name}, table {spec.table_id})."
    return api


__all__ = [
    "DatasetSpec",
    "dataset_api",
    "fetch_dataset",
    "get_dataset_info",
    "get_dataset_spec",
    "list_datasets",
    "list_dataset_specs",
    "process_dataset_frame",
    "register_dataset",
]

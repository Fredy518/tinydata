"""Batch markettable query helpers and public market dataset APIs."""

from __future__ import annotations

import time
from typing import Any, Iterable, Optional, Sequence

import pandas as pd

from .cache import CacheManager, make_cache_key
from .client import TinyClient
from .codes import normalize_codes, tinysoft_symbol_to_ts_code
from .datasets.specs import DatasetSpec, register_dataset
from .errors import TinyDataCodePoolError, TinyDataParameterError
from .infotable import chunked, parse_tinysoft_date
from .universe import resolve_universe


DEFAULT_MARKET_FIELDS = ("date", "StockID", "open", "high", "low", "close", "vol", "amount")
REQUIRED_MARKET_FIELDS = ("date", "StockID")

MARKET_FIELD_MAPPING = {
    "date": "trade_date",
    "StockID": "tsl_code",
    "stockid": "tsl_code",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "vol": "volume",
    "volume": "volume",
    "amount": "amount",
    "成交量": "volume",
    "成交额": "amount",
}

MARKET_QUERY_FIELD_ALIASES = {
    "trade_date": "date",
    "trade_time": "date",
    "tsl_code": "StockID",
    "ts_code": "StockID",
    "request_code": "StockID",
    "volume": "vol",
}


def _market_spec(
    name: str,
    domain: str,
    code_kind: Optional[str],
    cycle: str,
    *,
    priority: str = "P0",
    code_batch_size: int = 200,
) -> DatasetSpec:
    return register_dataset(
        DatasetSpec(
            name=name,
            domain=domain,
            priority=priority,
            table_id=0,
            source_table_name="markettable",
            source_kind="market",
            date_field="date",
            code_kind=code_kind,
            code_pool=code_kind,
            code_batch_size=code_batch_size,
            field_version="v1",
            safe_query_required=True,
            frequency=cycle,
            field_mapping=dict(MARKET_FIELD_MAPPING),
            date_columns=("trade_date",),
            numeric_columns=("open", "high", "low", "close", "volume", "amount"),
        )
    )


STOCK_DAILY = _market_spec("stock_daily", "stock", "stock", "日线", code_batch_size=300)
STOCK_WEEKLY = _market_spec("stock_weekly", "stock", "stock", "周线", priority="P1", code_batch_size=300)
STOCK_MONTHLY = _market_spec("stock_monthly", "stock", "stock", "月线", priority="P1", code_batch_size=300)
FUND_DAILY = _market_spec("fund_daily", "fund", "fund_market", "日线")
INDEX_DAILY = _market_spec("index_daily", "index", "index", "日线", code_batch_size=300)
CBOND_DAILY = _market_spec("cbond_daily", "bond", "bond", "日线", code_batch_size=300)
FUTURE_DAILY = _market_spec("future_daily", "future", "future", "日线")
OPTION_DAILY = _market_spec("option_daily", "option", "option", "日线")
HK_DAILY = _market_spec("hk_daily", "hk", None, "日线", priority="P2")


def _is_nonempty_codes(value: Optional[Iterable[Any]]) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _query_fields(fields: Optional[Sequence[Any]]) -> tuple[Any, ...]:
    requested = list(fields or DEFAULT_MARKET_FIELDS)
    out: list[Any] = []
    seen: set[str] = set()
    for field in (*REQUIRED_MARKET_FIELDS, *requested):
        text = MARKET_QUERY_FIELD_ALIASES.get(str(field or "").strip(), str(field or "").strip())
        key = text.lower()
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return tuple(out)


def _resolve_market_codes(
    *,
    symbols: Optional[Iterable[Any]],
    code_kind: Optional[str],
    refresh: bool,
    start_date: Any,
    end_date: Any,
    trade_date: Any,
    client: Optional[TinyClient],
    max_codes: Optional[int],
) -> list[str]:
    codes = normalize_codes(symbols, kind=code_kind) if _is_nonempty_codes(symbols) else []
    if not codes and code_kind:
        codes = resolve_universe(
            code_kind,
            refresh=refresh,
            start_date=start_date,
            end_date=end_date,
            trade_date=trade_date,
            client=client,
        )
    if max_codes is not None:
        codes = codes[: max(1, int(max_codes))]
    if not codes:
        raise TinyDataCodePoolError("Markettable query requires codes. Pass codes=... for this dataset.")
    return codes


def _exec_market_batch(
    client: TinyClient,
    *,
    codes: Sequence[str],
    cycle: str,
    start_time: Any,
    end_time: Any,
    fields: Sequence[Any],
    code_kind: Optional[str],
    timeout_ms: Optional[int],
    adjust: Any = None,
    adjust_date: Any = None,
    retries: int = 2,
) -> pd.DataFrame:
    last_error: Optional[Exception] = None
    for attempt in range(retries):
        try:
            return client.query_panel(
                stocks=codes,
                cycle=cycle,
                begin_time=start_time,
                end_time=end_time,
                fields=fields,
                code_kind=code_kind,
                timeout_ms=timeout_ms,
                adjust=adjust,
                adjust_date=adjust_date,
            )
        except Exception as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(0.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def _normalize_market_frame(df: pd.DataFrame, *, dataset: str, cycle: str, fields: Optional[Sequence[Any]]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    rename_map = {src: dst for src, dst in MARKET_FIELD_MAPPING.items() if src in out.columns}
    if rename_map:
        out.rename(columns=rename_map, inplace=True)
        out = out.loc[:, ~out.columns.duplicated()]

    if "tsl_code" not in out.columns:
        for source in ("StockID", "stockid", "证券代码", "code"):
            if source in out.columns:
                out["tsl_code"] = out[source]
                break
    if "request_code" not in out.columns and "tsl_code" in out.columns:
        out["request_code"] = out["tsl_code"]
    if "ts_code" not in out.columns and "tsl_code" in out.columns:
        out["ts_code"] = out["tsl_code"].map(tinysoft_symbol_to_ts_code)
    if "trade_date" in out.columns:
        parsed = out["trade_date"].map(parse_tinysoft_date)
        out["trade_time"] = parsed
        out["trade_date"] = parsed.map(lambda value: value.date() if not pd.isna(value) else pd.NaT)

    for col in ("open", "high", "low", "close", "volume", "amount"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    out["source_table_id"] = 0
    out["source_table_name"] = "markettable"
    out["cycle"] = cycle
    out["dataset"] = dataset

    base = {
        "trade_date",
        "trade_time",
        "tsl_code",
        "ts_code",
        "request_code",
        "source_table_id",
        "source_table_name",
        "cycle",
        "dataset",
    }
    if fields:
        mapped = {MARKET_FIELD_MAPPING.get(str(field), str(field)) for field in fields}
        keep = base | mapped
    else:
        keep = base | set(MARKET_FIELD_MAPPING.values())
    ordered = [col for col in out.columns if col in keep]
    return out[ordered]


def query_market_panel(
    symbols: Optional[Iterable[Any]] = None,
    start_time: Any = None,
    end_time: Any = None,
    *,
    codes: Optional[Iterable[Any]] = None,
    start_date: Any = None,
    end_date: Any = None,
    trade_date: Any = None,
    cycle: str = "日线",
    fields: Optional[Sequence[Any]] = None,
    refresh: bool = False,
    cache: bool = True,
    code_kind: Optional[str] = None,
    code_batch_size: int = 200,
    max_codes: Optional[int] = None,
    all_history: bool = False,
    dataset: str = "market_panel",
    client: Optional[TinyClient] = None,
    timeout_ms: Optional[int] = None,
    adjust: Any = None,
    adjust_date: Any = None,
) -> pd.DataFrame:
    """Query markettable for one or more symbols with batching and local cache."""

    if symbols is None and codes is not None:
        symbols = codes
    if trade_date is not None:
        start_date = trade_date
        end_date = trade_date
    begin = start_time or start_date
    end = end_time or end_date
    if not begin or not end:
        raise TinyDataParameterError("Markettable queries require start_date/end_date or start_time/end_time.")
    if not all_history:
        start_ts = parse_tinysoft_date(begin)
        end_ts = parse_tinysoft_date(end)
        if pd.isna(start_ts) or pd.isna(end_ts):
            raise TinyDataParameterError(f"Invalid markettable date range: {begin} to {end}")
        if start_ts > end_ts:
            raise TinyDataParameterError(f"Invalid markettable date range: {begin} is after {end}")

    try:
        adjust_rate = TinyClient._normalize_adjust_rate(adjust)
    except ValueError as exc:
        raise TinyDataParameterError(str(exc)) from exc
    if adjust_rate is None and adjust_date is not None:
        raise TinyDataParameterError("adjust_date requires adjust.")
    effective_adjust_date = adjust_date
    if adjust_rate is not None and effective_adjust_date is None:
        effective_adjust_date = end

    use_client = client or TinyClient()
    query_codes = _resolve_market_codes(
        symbols=symbols,
        code_kind=code_kind,
        refresh=refresh,
        start_date=begin,
        end_date=end,
        trade_date=trade_date,
        client=use_client,
        max_codes=max_codes,
    )
    query_fields = _query_fields(fields)
    batch_size = max(1, int(code_batch_size or 200))

    params = {
        "codes": query_codes,
        "start_time": begin,
        "end_time": end,
        "cycle": cycle,
        "fields": query_fields,
        "code_kind": code_kind,
        "code_batch_size": batch_size,
        "field_version": "v1",
        "adjust": adjust_rate,
        "adjust_date": effective_adjust_date,
    }
    manager = CacheManager()
    key = make_cache_key(dataset, params)
    if cache and not refresh:
        cached = manager.read(dataset, key)
        if cached is not None:
            return cached

    frames: list[pd.DataFrame] = []
    for batch in chunked(query_codes, batch_size):
        try:
            frame = _exec_market_batch(
                use_client,
                codes=batch,
                cycle=cycle,
                start_time=begin,
                end_time=end,
                fields=query_fields,
                code_kind=code_kind,
                timeout_ms=timeout_ms,
                adjust=adjust_rate,
                adjust_date=effective_adjust_date,
            )
        except Exception:
            if len(batch) == 1:
                raise
            singles = []
            for code in batch:
                one = _exec_market_batch(
                    use_client,
                    codes=[code],
                    cycle=cycle,
                    start_time=begin,
                    end_time=end,
                    fields=query_fields,
                    code_kind=code_kind,
                    timeout_ms=timeout_ms,
                    adjust=adjust_rate,
                    adjust_date=effective_adjust_date,
                )
                if one is not None and not one.empty:
                    if "StockID" not in one.columns and "stockid" not in one.columns:
                        one = one.copy()
                        one["StockID"] = code
                    singles.append(one)
            frame = pd.concat(singles, ignore_index=True) if singles else pd.DataFrame()
        if frame is not None and not frame.empty:
            frames.append(frame)

    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    processed = _normalize_market_frame(raw, dataset=dataset, cycle=cycle, fields=fields)
    if cache:
        manager.write(dataset, key, processed)
    return processed


def _market_api(name: str, code_kind: Optional[str], cycle: str, default_batch_size: int = 200):
    def api(
        codes: Optional[Iterable[Any]] = None,
        start_date: Any = None,
        end_date: Any = None,
        report_period: Any = None,
        trade_date: Any = None,
        refresh: bool = False,
        cache: bool = True,
        code_batch_size: Optional[int] = None,
        max_codes: Optional[int] = None,
        fields: Optional[Sequence[Any]] = None,
        all_history: bool = False,
        adjust: Any = None,
        adjust_date: Any = None,
    ) -> pd.DataFrame:
        effective_trade_date = trade_date if trade_date is not None else report_period
        return query_market_panel(
            codes=codes,
            start_date=start_date,
            end_date=end_date,
            trade_date=effective_trade_date,
            cycle=cycle,
            fields=fields,
            refresh=refresh,
            cache=cache,
            code_kind=code_kind,
            code_batch_size=code_batch_size or default_batch_size,
            max_codes=max_codes,
            all_history=all_history,
            dataset=name,
            adjust=adjust,
            adjust_date=adjust_date,
        )

    api.__name__ = name
    api.__doc__ = f"Fetch Tinysoft markettable dataset {name}."
    return api


stock_daily = _market_api("stock_daily", "stock", "日线", 300)
stock_weekly = _market_api("stock_weekly", "stock", "周线", 300)
stock_monthly = _market_api("stock_monthly", "stock", "月线", 300)
fund_daily = _market_api("fund_daily", "fund_market", "日线", 200)
index_daily = _market_api("index_daily", "index", "日线", 300)
cbond_daily = _market_api("cbond_daily", "bond", "日线", 300)
future_daily = _market_api("future_daily", "future", "日线", 200)
option_daily = _market_api("option_daily", "option", "日线", 200)
hk_daily = _market_api("hk_daily", None, "日线", 200)


__all__ = [
    "CBOND_DAILY",
    "DEFAULT_MARKET_FIELDS",
    "FUND_DAILY",
    "FUTURE_DAILY",
    "HK_DAILY",
    "INDEX_DAILY",
    "MARKET_FIELD_MAPPING",
    "OPTION_DAILY",
    "STOCK_DAILY",
    "STOCK_MONTHLY",
    "STOCK_WEEKLY",
    "cbond_daily",
    "fund_daily",
    "future_daily",
    "hk_daily",
    "index_daily",
    "option_daily",
    "query_market_panel",
    "stock_daily",
    "stock_monthly",
    "stock_weekly",
]

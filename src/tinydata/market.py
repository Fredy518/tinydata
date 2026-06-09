"""Batch markettable query helpers and public market dataset APIs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import time
from typing import Any, Iterable, Optional, Sequence

import pandas as pd

from .cache import CacheManager, make_cache_key
from .client import TinyClient
from .codes import normalize_codes, tinysoft_symbol_series_to_ts_code
from .datasets.specs import DatasetSpec, register_dataset
from .errors import TinyDataCodePoolError, TinyDataParameterError, TinyDataRateLimitError
from .infotable import chunked, parse_tinysoft_date, quote_tsl_string
from .parallel import run_parallel_code_queries
from .progress import _create_progress_tracker
from .universe import resolve_universe

logger = logging.getLogger(__name__)


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
HK_DAILY = _market_spec("hk_daily", "hk", None, "日线", priority="P0")

HK_CONNECT_EXCHANGE_RATE = register_dataset(
    DatasetSpec(
        name="hk_connect_exchange_rate",
        domain="hk",
        priority="P0",
        table_id=0,
        source_table_name="港股通参考/结算汇率",
        source_kind="tsl_function",
        date_field="date",
        code_kind=None,
        code_pool=None,
        code_batch_size=2,
        field_version="v1",
        safe_query_required=True,
        frequency="daily",
        field_mapping={
            "代码": "fx_code",
            "截止日": "trade_date",
            "参考汇率买入价": "reference_buy_rate",
            "参考汇率卖出价": "reference_sell_rate",
            "参考汇率中间价": "reference_middle_rate",
            "买入结算汇率": "settlement_buy_rate",
            "卖出结算汇率": "settlement_sell_rate",
            "结算汇率中间价": "settlement_middle_rate",
        },
        date_columns=("trade_date",),
        numeric_columns=(
            "reference_buy_rate",
            "reference_sell_rate",
            "reference_middle_rate",
            "settlement_buy_rate",
            "settlement_sell_rate",
            "settlement_middle_rate",
        ),
    )
)


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
            include_inactive=False if code_kind == "stock" else None,
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


def _fetch_market_batch(
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
) -> pd.DataFrame:
    try:
        return _exec_market_batch(
            client,
            codes=codes,
            cycle=cycle,
            start_time=start_time,
            end_time=end_time,
            fields=fields,
            code_kind=code_kind,
            timeout_ms=timeout_ms,
            adjust=adjust,
            adjust_date=adjust_date,
        )
    except TinyDataRateLimitError:
        raise
    except Exception:
        if len(codes) == 1:
            raise
        singles = []
        for code in codes:
            one = _exec_market_batch(
                client,
                codes=[code],
                cycle=cycle,
                start_time=start_time,
                end_time=end_time,
                fields=fields,
                code_kind=code_kind,
                timeout_ms=timeout_ms,
                adjust=adjust,
                adjust_date=adjust_date,
            )
            if one is not None and not one.empty:
                if "StockID" not in one.columns and "stockid" not in one.columns:
                    one = one.copy()
                    one["StockID"] = code
                singles.append(one)
        return pd.concat(singles, ignore_index=True) if singles else pd.DataFrame()


def _normalize_max_workers(max_workers: Optional[int], *, batch_count: int) -> int:
    if max_workers is None:
        return 1
    workers = int(max_workers)
    if workers < 1:
        raise TinyDataParameterError("max_workers must be >= 1.")
    if batch_count <= 0:
        return workers
    return min(workers, batch_count)


def _reduced_max_workers(worker_count: int) -> int:
    if worker_count <= 1:
        return 1
    reduced = max(1, worker_count // 2)
    if reduced == worker_count:
        reduced = worker_count - 1
    return reduced


def _parse_market_trade_dates(values: pd.Series) -> pd.Series:
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
        out["ts_code"] = tinysoft_symbol_series_to_ts_code(out["tsl_code"])
    if "trade_date" in out.columns:
        parsed = _parse_market_trade_dates(out["trade_date"])
        out["trade_time"] = parsed
        out["trade_date"] = parsed.dt.date

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


def _realtime_window(*, end_time: Any, window_minutes: float) -> tuple[pd.Timestamp, pd.Timestamp]:
    try:
        minutes = float(window_minutes)
    except (TypeError, ValueError) as exc:
        raise TinyDataParameterError("window_minutes must be a positive number.") from exc
    if minutes <= 0:
        raise TinyDataParameterError("window_minutes must be a positive number.")

    if end_time is None:
        end_ts = pd.Timestamp.now()
    else:
        end_ts = parse_tinysoft_date(end_time)
        if pd.isna(end_ts):
            raise TinyDataParameterError(f"Invalid realtime end_time: {end_time}")
    start_ts = end_ts - pd.Timedelta(minutes=minutes)
    return start_ts, end_ts


def realtime_bar(
    codes: Iterable[Any],
    *,
    window_minutes: float = 5,
    end_time: Any = None,
    cycle: str = "1分钟线",
    fields: Optional[Sequence[Any]] = None,
    code_kind: Optional[str] = "stock",
    code_batch_size: int = 200,
    max_workers: Optional[int] = None,
    progress: Optional[bool] = None,
    max_codes: Optional[int] = None,
    client: Optional[TinyClient] = None,
    timeout_ms: Optional[int] = None,
) -> pd.DataFrame:
    """Fetch recent markettable bars for explicitly supplied codes."""

    query_codes = normalize_codes(codes, kind=code_kind)
    if not query_codes:
        raise TinyDataParameterError("realtime_bar requires one or more codes.")
    start_ts, end_ts = _realtime_window(end_time=end_time, window_minutes=window_minutes)
    return query_market_panel(
        codes=query_codes,
        start_time=start_ts,
        end_time=end_ts,
        cycle=cycle,
        fields=fields,
        refresh=True,
        cache=False,
        code_kind=code_kind,
        code_batch_size=code_batch_size,
        max_workers=max_workers,
        progress=progress,
        max_codes=max_codes,
        dataset="realtime_bar",
        client=client,
        timeout_ms=timeout_ms,
    )


def realtime_snapshot(
    codes: Iterable[Any],
    *,
    window_minutes: float = 240,
    end_time: Any = None,
    cycle: str = "1分钟线",
    fields: Optional[Sequence[Any]] = None,
    code_kind: Optional[str] = "stock",
    code_batch_size: int = 200,
    max_workers: Optional[int] = None,
    progress: Optional[bool] = None,
    max_codes: Optional[int] = None,
    client: Optional[TinyClient] = None,
    timeout_ms: Optional[int] = None,
) -> pd.DataFrame:
    """Fetch recent bars and keep the latest row for each requested code."""

    bars = realtime_bar(
        codes,
        window_minutes=window_minutes,
        end_time=end_time,
        cycle=cycle,
        fields=fields,
        code_kind=code_kind,
        code_batch_size=code_batch_size,
        max_workers=max_workers,
        progress=progress,
        max_codes=max_codes,
        client=client,
        timeout_ms=timeout_ms,
    )
    if bars.empty or "tsl_code" not in bars.columns:
        return bars

    out = bars.copy()
    order = {code: idx for idx, code in enumerate(normalize_codes(codes, kind=code_kind))}
    out["_tinydata_order"] = out["tsl_code"].map(order).fillna(len(order))
    sort_cols = ["_tinydata_order"]
    if "trade_time" in out.columns:
        sort_cols.append("trade_time")
    latest = out.sort_values(sort_cols, na_position="first").groupby("tsl_code", sort=False).tail(1)
    return latest.drop(columns=["_tinydata_order"]).reset_index(drop=True)


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
    max_workers: Optional[int] = None,
    progress: Optional[bool] = None,
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
    batches = chunked(query_codes, batch_size)
    worker_count = _normalize_max_workers(max_workers, batch_count=len(batches))

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

    batch_frames: list[Optional[pd.DataFrame]] = [None] * len(batches)
    pending_batches = list(enumerate(batches))
    current_workers = worker_count

    with _create_progress_tracker(
        enabled=progress,
        total=len(batch_frames),
        description=f"{dataset} batches",
    ) as progress_tracker:
        while pending_batches:
            if current_workers > 1 and len(pending_batches) > 1:
                rate_limited: list[tuple[int, list[str]]] = []
                with ThreadPoolExecutor(max_workers=current_workers) as executor:
                    future_map = {
                        executor.submit(
                            _fetch_market_batch,
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
                        ): (idx, batch)
                        for idx, batch in pending_batches
                    }
                    for future in as_completed(future_map):
                        idx, batch = future_map[future]
                        try:
                            batch_frames[idx] = future.result()
                            progress_tracker.update()
                        except TinyDataRateLimitError:
                            rate_limited.append((idx, batch))
                        except Exception:
                            raise

                if rate_limited:
                    next_workers = _reduced_max_workers(current_workers)
                    if next_workers >= current_workers:
                        raise TinyDataRateLimitError("Tinysoft OPI HTTP 429: unable to reduce market query concurrency further.")
                    logger.warning(
                        "Tinysoft OPI returned HTTP 429 during parallel market batches; retrying %s failed batch(es) with max_workers=%s.",
                        len(rate_limited),
                        next_workers,
                    )
                    pending_batches = rate_limited
                    current_workers = next_workers
                    continue

                break

            for idx, batch in pending_batches:
                batch_frames[idx] = _fetch_market_batch(
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
                progress_tracker.update()
            break

    frames: list[pd.DataFrame] = []
    for frame in batch_frames:
        if frame is not None and not frame.empty:
            frames.append(frame)

    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    processed = _normalize_market_frame(raw, dataset=dataset, cycle=cycle, fields=fields)
    if cache:
        manager.write(dataset, key, processed)
    return processed


HK_CONNECT_RATE_CODES = ("FXHGTCNY", "FXSGTCNY")
HK_CONNECT_RATE_FUNCTIONS = (
    ("参考汇率买入价", "StockGGTExBuyPrice"),
    ("参考汇率卖出价", "StockGGTExSellPrice"),
    ("参考汇率中间价", "StockGGTExMiddlePrice"),
    ("买入结算汇率", "StockGGTExBuyRate"),
    ("卖出结算汇率", "StockGGTExSellRate"),
    ("结算汇率中间价", "StockGGTExMiddleRate"),
)


def _normalize_hk_connect_rate_codes(codes: Optional[Iterable[Any]]) -> list[str]:
    if not _is_nonempty_codes(codes):
        return list(HK_CONNECT_RATE_CODES)
    normalized = [str(code or "").strip().upper() for code in normalize_codes(codes, kind=None)]
    normalized = [code for code in normalized if code]
    allowed = set(HK_CONNECT_RATE_CODES)
    unknown = [code for code in normalized if code not in allowed]
    if unknown:
        raise TinyDataParameterError(
            f"hk_connect_exchange_rate only supports {sorted(allowed)}; unknown codes: {unknown}."
        )
    return list(dict.fromkeys(normalized))


def _market_date_range(*, start_date: Any = None, end_date: Any = None, trade_date: Any = None) -> list[str]:
    if trade_date is not None:
        start_date = trade_date
        end_date = trade_date
    if start_date in (None, "") or end_date in (None, ""):
        raise TinyDataParameterError("hk_connect_exchange_rate requires trade_date or start_date/end_date.")
    start = parse_tinysoft_date(start_date)
    end = parse_tinysoft_date(end_date)
    if pd.isna(start) or pd.isna(end):
        raise TinyDataParameterError(f"Invalid hk_connect_exchange_rate date range: {start_date} to {end_date}")
    if start > end:
        raise TinyDataParameterError(f"Invalid hk_connect_exchange_rate date range: {start_date} is after {end_date}")
    return [dt.strftime("%Y%m%d") for dt in pd.date_range(start.normalize(), end.normalize(), freq="D")]


def _extract_scalar_values(payload: Any) -> list[Any]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, pd.DataFrame):
        if payload.empty:
            return []
        if len(payload.columns) == 1:
            return payload.iloc[:, 0].tolist()
        return payload.iloc[0].tolist()
    if isinstance(payload, dict):
        for key in ("data", "Data", "value", "Value"):
            if key in payload:
                value = payload[key]
                return value if isinstance(value, list) else [value]
        return [payload]
    return [payload]


def _build_hk_connect_rate_tsl(code: str, date: str) -> str:
    calls = ",".join(f"{func_name}()" for _, func_name in HK_CONNECT_RATE_FUNCTIONS)
    return (
        f"setsysparam(pn_stock(),{quote_tsl_string(code)});"
        f"setsysparam(pn_date(),{date}T);"
        f"return array({calls});"
    )


def hk_connect_exchange_rate(
    codes: Optional[Iterable[Any]] = None,
    start_date: Any = None,
    end_date: Any = None,
    trade_date: Any = None,
    *,
    refresh: bool = False,
    cache: bool = True,
    max_workers: Optional[int] = None,
    progress: Optional[bool] = None,
) -> pd.DataFrame:
    """Fetch Hong Kong Stock Connect reference and settlement exchange rates."""

    query_codes = _normalize_hk_connect_rate_codes(codes)
    query_dates = _market_date_range(start_date=start_date, end_date=end_date, trade_date=trade_date)
    params = {
        "codes": query_codes,
        "dates": query_dates,
        "field_version": HK_CONNECT_EXCHANGE_RATE.field_version,
    }
    manager = CacheManager()
    key = make_cache_key(HK_CONNECT_EXCHANGE_RATE.name, params)
    if cache and not refresh:
        cached = manager.read(HK_CONNECT_EXCHANGE_RATE.name, key)
        if cached is not None:
            return cached

    client = TinyClient()
    tasks = [f"{code}|{date}" for code in query_codes for date in query_dates]

    def fetch_one(task: str) -> dict[str, Any] | None:
        code, date = task.split("|", 1)
        values = _extract_scalar_values(client.exec(_build_hk_connect_rate_tsl(code, date), as_dataframe=False))
        row: dict[str, Any] = {"代码": code, "截止日": date}
        for idx, (source_name, _) in enumerate(HK_CONNECT_RATE_FUNCTIONS):
            row[source_name] = values[idx] if idx < len(values) else None
        return row

    rows = run_parallel_code_queries(
        tasks,
        fetch_one=fetch_one,
        max_workers=max_workers,
        progress=progress,
        description=f"{HK_CONNECT_EXCHANGE_RATE.name} dates",
        logger=logger,
        rate_limit_scope=f"parallel {HK_CONNECT_EXCHANGE_RATE.name} queries",
    )
    raw = pd.DataFrame(rows)
    if raw.empty:
        out = pd.DataFrame()
    else:
        out = raw.rename(columns=HK_CONNECT_EXCHANGE_RATE.field_mapping)
        out["trade_date"] = pd.to_datetime(out["trade_date"], format="%Y%m%d", errors="coerce").dt.date
        for column in HK_CONNECT_EXCHANGE_RATE.numeric_columns:
            if column in out.columns:
                out[column] = pd.to_numeric(out[column], errors="coerce")
        out["request_code"] = out["fx_code"]
        out["source_table_id"] = HK_CONNECT_EXCHANGE_RATE.table_id
        out["source_table_name"] = HK_CONNECT_EXCHANGE_RATE.source_table_name
    if cache:
        manager.write(HK_CONNECT_EXCHANGE_RATE.name, key, out)
    return out


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
        max_workers: Optional[int] = None,
        progress: Optional[bool] = None,
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
            max_workers=max_workers,
            progress=progress,
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
    "HK_CONNECT_EXCHANGE_RATE",
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
    "hk_connect_exchange_rate",
    "hk_daily",
    "index_daily",
    "option_daily",
    "query_market_panel",
    "realtime_bar",
    "realtime_snapshot",
    "stock_daily",
    "stock_monthly",
    "stock_weekly",
]

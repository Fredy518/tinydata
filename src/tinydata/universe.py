"""OPI-backed security universe helpers.

The functions in this module are the default code-pool source for dataset
APIs.  They intentionally avoid AlphaHome imports and keep local CSV files as
fallback only.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Optional

import pandas as pd

from .cache import CacheManager, make_cache_key
from .client import TinyClient
from .codes import load_code_pool, normalize_codes
from .errors import TinyDataCodePoolError
from .infotable import InfoTableOptions, build_where_clause, format_select_fields, query_infotable, quote_tsl_string

MARKET_CODES = ["SH000001", "SZ399001", "QI000001", "HKHSI001", "HSG000001", "HSG000002", "CBICBA00301"]
HSGT_CHANNEL_CODES = ["HG000001", "HG000002", "HG000003", "HG000004"]
MARGIN_MARKET_CODES = ["RZRQ000001", "RZRQ000002", "RZRQ000003"]
FUND_MARKET_BLOCKS = ("上证基金", "深证基金", "上证ETF", "深证ETF")

_FINANCIAL_OPTION_EXCHANGES = {"上海证券交易所", "深圳证券交易所", "中国金融期货交易所", "SSE", "SZSE", "CFFEX"}
logger = logging.getLogger(__name__)


def _warn_universe_fallback(name: str, exc: Exception, fallback: str = "local CSV") -> None:
    logger.warning(
        "OPI universe '%s' load failed; falling back to %s. error=%s: %s",
        name,
        fallback,
        type(exc).__name__,
        exc,
    )


def _first_present(row: pd.Series, columns: Iterable[str]) -> Any:
    for col in columns:
        if col in row.index:
            value = row.get(col)
            if pd.notna(value) and str(value).strip():
                return value
    return None


def _frame_to_codes(df: pd.DataFrame, columns: Iterable[str], *, kind: Optional[str] = None) -> list[str]:
    if df is None or df.empty:
        return []
    out: list[str] = []
    for _, row in df.iterrows():
        value = _first_present(row, columns)
        if value is None:
            continue
        out.extend(normalize_codes([value], kind=kind))
    return list(dict.fromkeys(code for code in out if code))


def _cached_codes(
    name: str,
    params: dict[str, Any],
    *,
    refresh: bool,
    loader,
) -> list[str]:
    manager = CacheManager()
    key = make_cache_key(name, params, namespace="universe")
    if not refresh:
        cached = manager.read(name, key, namespace="universe")
        if cached is not None and "code" in cached.columns:
            return [str(x) for x in cached["code"].dropna().tolist()]
    codes = loader()
    if codes:
        manager.write(name, key, pd.DataFrame({"code": codes}), namespace="universe")
    return codes


def _query_universe_table(
    *,
    table_id: int,
    fields: list[str],
    kind: Optional[str],
    date_field: Optional[str] = None,
    start_date: Any = None,
    end_date: Any = None,
    client: Optional[TinyClient] = None,
) -> pd.DataFrame:
    return query_infotable(
        client or TinyClient(),
        table_id,
        fields=fields,
        start_date=start_date,
        end_date=end_date,
        date_field=date_field,
        allow_full_table=True,
        options=InfoTableOptions(code_kind=kind, code_batch_size=2000, retries=1),
    )


def _query_block_table(
    *,
    block_name: str,
    table_id: int,
    fields: list[str],
    date_field: Optional[str] = None,
    start_date: Any = None,
    end_date: Any = None,
    client: Optional[TinyClient] = None,
    timeout_ms: Optional[int] = None,
) -> pd.DataFrame:
    where_clause = build_where_clause(start_date=start_date, end_date=end_date, date_field=date_field)
    where_part = f" where {where_clause}" if where_clause else ""
    tsl = (
        f"return select {format_select_fields(fields)} from infotable {int(table_id)} "
        f"of GetBk({quote_tsl_string(block_name)}){where_part} end;"
    )
    return (client or TinyClient()).exec(tsl, as_dataframe=True, timeout_ms=timeout_ms)


def _fallback_local(name: str, *, columns: tuple[str, ...] = ("ts_code", "code", "symbol")) -> list[str]:
    return load_code_pool(name, columns=columns)


def _raise_missing(name: str) -> None:
    raise TinyDataCodePoolError(
        f"Unable to build OPI universe '{name}'. Pass codes=... or provide ~/.tinydata/codes/{name}.csv."
    )


def stock_codes(*, refresh: bool = False, include_inactive: bool = True, client: Optional[TinyClient] = None) -> list[str]:
    def load() -> list[str]:
        try:
            # getbk("A股") is a current board and can miss delisted names.
            # Use 股票.基本信息 as the historical stock-code universe, with the
            # current-board query kept as a fallback for tenants that reject
            # full-table access.
            df = _query_universe_table(
                table_id=10,
                fields=["StockID", "证券代码", "A股代码", "当前状态"],
                kind="stock",
                client=client,
            )
        except Exception as exc:
            _warn_universe_fallback("stock_full_table", exc, "current A股 board/local CSV")
            try:
                df = _query_block_table(
                    block_name="A股",
                    table_id=10,
                    fields=["StockID", "证券代码", "A股代码", "当前状态"],
                    client=client,
                )
            except Exception as inner_exc:
                _warn_universe_fallback("stock", inner_exc)
                return _fallback_local("stock")
        try:
            codes = _frame_to_codes(df, ["StockID", "stockid", "证券代码", "A股代码"], kind="stock")
            if not include_inactive and "当前状态" in df.columns and codes:
                status = df["当前状态"].astype(str)
                active = status.str.contains("上市|正常|交易", na=False)
                inactive = status.str.contains("终止|退市|暂停|未上市|摘牌|停止", na=False)
                active_rows = df[active & ~inactive]
                codes = _frame_to_codes(active_rows, ["StockID", "stockid", "证券代码", "A股代码"], kind="stock")
            return codes
        except Exception as exc:
            _warn_universe_fallback("stock", exc)
            return _fallback_local("stock")

    codes = _cached_codes("stock", {"include_inactive": include_inactive, "v": 2}, refresh=refresh, loader=load)
    if not codes:
        _raise_missing("stock")
    return codes


def fund_codes(*, refresh: bool = False, include_inactive: bool = True, client: Optional[TinyClient] = None) -> list[str]:
    def load() -> list[str]:
        try:
            df = _query_block_table(
                block_name="开放式基金",
                table_id=302,
                fields=["StockID", "证券代码", "基金类型", "基金名称", "基金简称", "清算日"],
                client=client,
            )
            if not include_inactive and "清算日" in df.columns:
                df = df[df["清算日"].isna() | (df["清算日"].astype(str).str.strip() == "")]
            return _frame_to_codes(df, ["StockID", "stockid", "证券代码"], kind="fund")
        except Exception as exc:
            _warn_universe_fallback("fund", exc)
            return _fallback_local("fund")

    codes = _cached_codes("fund", {"include_inactive": include_inactive, "v": 1}, refresh=refresh, loader=load)
    if not codes:
        _raise_missing("fund")
    return codes


def fof_fund_codes(*, refresh: bool = False, client: Optional[TinyClient] = None) -> list[str]:
    def load() -> list[str]:
        try:
            df = _query_block_table(
                block_name="开放式基金",
                table_id=302,
                fields=["StockID", "证券代码", "基金类型", "基金名称", "基金简称", "投资类型"],
                client=client,
            )
            text_cols = [col for col in ("基金类型", "基金名称", "基金简称", "投资类型") if col in df.columns]
            if text_cols:
                text = df[text_cols].astype(str).agg(" ".join, axis=1).str.upper()
                df = df[text.str.contains("FOF|基金中基金", regex=True, na=False)]
            codes = _frame_to_codes(df, ["StockID", "stockid", "证券代码"], kind="fund")
            return codes or _fallback_local("fof_fund")
        except Exception as exc:
            _warn_universe_fallback("fof_fund", exc)
            return _fallback_local("fof_fund")

    codes = _cached_codes("fof_fund", {"v": 1}, refresh=refresh, loader=load)
    if not codes:
        _raise_missing("fof_fund")
    return codes


def fund_market_codes(
    *,
    refresh: bool = False,
    include_inactive: bool = True,
    client: Optional[TinyClient] = None,
) -> list[str]:
    def load() -> list[str]:
        frames: list[pd.DataFrame] = []
        for block_name in FUND_MARKET_BLOCKS:
            try:
                frames.append(
                    _query_block_table(
                        block_name=block_name,
                        table_id=302,
                        fields=["StockID", "证券代码", "交易代码", "基金名称", "基金简称", "清算日"],
                        client=client,
                    )
                )
            except Exception as exc:
                _warn_universe_fallback(f"fund_market:{block_name}", exc, "next block/local CSV")
                continue
        if not frames:
            return _fallback_local("fund_market")
        df = pd.concat(frames, ignore_index=True)
        if not include_inactive and "清算日" in df.columns:
            df = df[df["清算日"].isna() | (df["清算日"].astype(str).str.strip() == "")]
        codes = _frame_to_codes(df, ["StockID", "stockid", "交易代码", "证券代码"], kind=None)
        market_codes = [code for code in codes if code.startswith(("SH", "SZ", "BJ"))]
        return market_codes or _fallback_local("fund_market")

    codes = _cached_codes("fund_market", {"include_inactive": include_inactive, "v": 1}, refresh=refresh, loader=load)
    if not codes:
        _raise_missing("fund_market")
    return codes


def bond_codes(*, refresh: bool = False, include_inactive: bool = True, client: Optional[TinyClient] = None) -> list[str]:
    def load() -> list[str]:
        try:
            df = _query_block_table(
                block_name="可转债",
                table_id=502,
                fields=["StockID", "债券代码", "债券简称", "摘牌日"],
                client=client,
            )
            if not include_inactive and "摘牌日" in df.columns:
                df = df[df["摘牌日"].isna() | (df["摘牌日"].astype(str).str.strip() == "")]
            return _frame_to_codes(df, ["StockID", "stockid", "债券代码"], kind="bond")
        except Exception as exc:
            _warn_universe_fallback("bond", exc)
            return _fallback_local("bond")

    codes = _cached_codes("bond", {"include_inactive": include_inactive, "v": 1}, refresh=refresh, loader=load)
    if not codes:
        _raise_missing("bond")
    return codes


def index_codes(*, refresh: bool = False, include_inactive: bool = True, client: Optional[TinyClient] = None) -> list[str]:
    def load() -> list[str]:
        try:
            df = _query_universe_table(
                table_id=750,
                fields=["StockID", "证券代码", "指数代码", "指数简称", "停用日期"],
                kind="index",
                client=client,
            )
            if not include_inactive and "停用日期" in df.columns:
                df = df[df["停用日期"].isna() | (df["停用日期"].astype(str).str.strip() == "")]
            return _frame_to_codes(df, ["StockID", "stockid", "证券代码", "指数代码"], kind="index")
        except Exception as exc:
            _warn_universe_fallback("index", exc, "local CSV/default index sample")
            codes = _fallback_local("index")
            return codes or ["SH000001", "SZ399006", "CSI000300", "CSI000500", "CSI000905"]

    return _cached_codes("index", {"include_inactive": include_inactive, "v": 1}, refresh=refresh, loader=load)


def future_codes(*, refresh: bool = False, include_inactive: bool = True, client: Optional[TinyClient] = None) -> list[str]:
    def load() -> list[str]:
        try:
            df = _query_block_table(
                block_name="股指期货",
                table_id=703,
                fields=["StockID", "合约代码", "最后交易日"],
                client=client,
            )
            return _frame_to_codes(df, ["StockID", "stockid", "合约代码"], kind="future")
        except Exception as exc:
            _warn_universe_fallback("future", exc)
            return _fallback_local("future")

    codes = _cached_codes("future", {"include_inactive": include_inactive, "v": 1}, refresh=refresh, loader=load)
    if not codes:
        _raise_missing("future")
    return codes


def future_product_codes(*, refresh: bool = False, client: Optional[TinyClient] = None) -> list[str]:
    def load() -> list[str]:
        try:
            df = _query_universe_table(
                table_id=708,
                fields=["StockID", "品种代码", "品种名称"],
                kind="future_product",
                client=client,
            )
            return _frame_to_codes(df, ["StockID", "stockid", "品种代码"], kind="future_product")
        except Exception as exc:
            _warn_universe_fallback("future_product", exc, "local CSV/derived futures products")
            local = _fallback_local("future_product")
            if local:
                return local
            try:
                import re

                products = []
                for code in future_codes(refresh=refresh, client=client):
                    match = re.match(r"^[A-Z]+", code.upper())
                    if match:
                        products.append(match.group(0))
                return list(dict.fromkeys(products))
            except Exception as inner_exc:
                _warn_universe_fallback("future_product_derived", inner_exc, "empty code pool")
                return []

    codes = _cached_codes("future_product", {"v": 1}, refresh=refresh, loader=load)
    if not codes:
        _raise_missing("future_product")
    return codes


def option_codes(
    *,
    trade_date: Any = None,
    start_date: Any = None,
    end_date: Any = None,
    refresh: bool = False,
    include_inactive: bool = True,
    client: Optional[TinyClient] = None,
) -> list[str]:
    def load() -> list[str]:
        frames = []
        for block_name in ("ETF期权", "中金所期权"):
            try:
                frames.append(
                    _query_block_table(
                        block_name=block_name,
                        table_id=720,
                        fields=["StockID", "合约交易代码", "上市地", "截止日"],
                        date_field="截止日",
                        start_date=trade_date or start_date,
                        end_date=trade_date or end_date,
                        client=client,
                        timeout_ms=30_000,
                    )
                )
            except Exception as exc:
                _warn_universe_fallback(f"option:{block_name}", exc, "next block/local CSV")
                continue
        if not frames:
            return _fallback_local("option")
        df = pd.concat(frames, ignore_index=True)
        if "上市地" in df.columns:
            mask = df["上市地"].astype(str).isin(_FINANCIAL_OPTION_EXCHANGES)
            if mask.any():
                df = df[mask]
        return _frame_to_codes(df, ["StockID", "stockid", "合约交易代码"], kind="option")

    params = {"trade_date": trade_date, "start_date": start_date, "end_date": end_date, "include_inactive": include_inactive, "v": 1}
    codes = _cached_codes("option", params, refresh=refresh, loader=load)
    if not codes:
        _raise_missing("option")
    return codes


def market_codes(*, refresh: bool = False, client: Optional[TinyClient] = None) -> list[str]:
    return MARKET_CODES.copy()


def margin_market_codes(*, refresh: bool = False, client: Optional[TinyClient] = None) -> list[str]:
    return MARGIN_MARKET_CODES.copy()


def resolve_universe(
    kind: Optional[str],
    *,
    refresh: bool = False,
    start_date: Any = None,
    end_date: Any = None,
    trade_date: Any = None,
    client: Optional[TinyClient] = None,
) -> list[str]:
    if kind in (None, "", "none"):
        return []
    if kind == "stock":
        return stock_codes(refresh=refresh, client=client)
    if kind == "fund":
        return fund_codes(refresh=refresh, client=client)
    if kind == "fund_market":
        return fund_market_codes(refresh=refresh, client=client)
    if kind == "fof_fund":
        return fof_fund_codes(refresh=refresh, client=client)
    if kind == "bond":
        return bond_codes(refresh=refresh, client=client)
    if kind == "index":
        return index_codes(refresh=refresh, client=client)
    if kind == "future":
        return future_codes(refresh=refresh, client=client)
    if kind == "future_product":
        return future_product_codes(refresh=refresh, client=client)
    if kind == "option":
        return option_codes(trade_date=trade_date, start_date=start_date, end_date=end_date, refresh=refresh, client=client)
    if kind == "market":
        return market_codes(refresh=refresh, client=client)
    if kind == "margin_market":
        return margin_market_codes(refresh=refresh, client=client)
    if kind == "hsgt_channel":
        return HSGT_CHANNEL_CODES.copy()
    if kind == "hsgt_stock":
        return [code for code in stock_codes(refresh=refresh, client=client) if code.startswith(("SH", "SZ"))]
    return _fallback_local(kind)


__all__ = [
    "bond_codes",
    "fof_fund_codes",
    "fund_codes",
    "fund_market_codes",
    "future_codes",
    "future_product_codes",
    "index_codes",
    "margin_market_codes",
    "market_codes",
    "option_codes",
    "resolve_universe",
    "stock_codes",
]

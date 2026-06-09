"""Futures dataset APIs."""

from __future__ import annotations

import re
from typing import Any, Optional, Sequence

import pandas as pd

from ..codes import normalize_codes
from ..errors import TinyDataParameterError
from .specs import DatasetSpec, dataset_api, fetch_dataset, register_dataset


FUTURE_BASIC_EXT = register_dataset(
    DatasetSpec(
        name="future_basic_ext",
        domain="future",
        priority="P0",
        table_id=703,
        source_table_name="期货.期货基本信息",
        date_field="变动日",
        code_kind="future",
        code_pool="future",
        code_batch_size=1000,
        postprocess="future",
        field_mapping={
            "StockID": "source_code",
            "stockid": "source_code",
            "合约代码": "contract_code_raw",
            "变动日": "change_date",
            "交易代码": "product_code",
            "交割年份": "delivery_year",
            "交割月份": "delivery_month",
            "交易品种": "product_name",
            "合约乘数": "contract_multiplier",
            "合约乘数单位": "contract_multiplier_unit",
            "报价单位": "quote_unit",
            "最小变动价位": "min_price_change",
            "每日价格最大波动下限(%)": "daily_price_limit_down_pct",
            "每日价格最大波动上限(%)": "daily_price_limit_up_pct",
            "最后交易日参照标准": "last_trade_ref_standard",
            "最后交易日相对参照标准偏移月份": "last_trade_ref_offset_months",
            "最后交易日类别": "last_trade_day_type",
            "最后交易日相对最后交易日所在月份偏移天数": "last_trade_offset_days",
            "最后交易日是否假日顺延": "last_trade_holiday_adjust",
            "最后交易日": "last_trade_date",
            "最后交割日参照标准": "last_delivery_ref_standard",
            "最后交割日相对参照标准偏移月份": "last_delivery_ref_offset_months",
            "最后交割日类别": "last_delivery_day_type",
            "最后交割日相对最后交割日所在月份偏移天数": "last_delivery_offset_days",
            "最后交割日是否假日顺延": "last_delivery_holiday_adjust",
            "最后交割日": "last_delivery_date",
            "最低交易保证金(%)": "min_trade_margin_pct",
            "交割方式": "delivery_method",
            "上市地": "exchange_name",
            "期货类别": "future_category",
            "商品期货类别": "commodity_category",
            "基准代码": "benchmark_code",
        },
        date_columns=("change_date", "last_trade_date", "last_delivery_date"),
        numeric_columns=(
            "delivery_year",
            "delivery_month",
            "contract_multiplier",
            "min_price_change",
            "daily_price_limit_down_pct",
            "daily_price_limit_up_pct",
            "last_trade_ref_offset_months",
            "last_trade_offset_days",
            "last_delivery_ref_offset_months",
            "last_delivery_offset_days",
            "min_trade_margin_pct",
        ),
        integer_columns=(
            "delivery_year",
            "delivery_month",
            "last_trade_ref_offset_months",
            "last_trade_offset_days",
            "last_delivery_ref_offset_months",
            "last_delivery_offset_days",
        ),
        extra_columns=("ts_code",),
    )
)

FUTURE_PRODUCT_MAPPING_EXT = register_dataset(
    DatasetSpec(
        name="future_product_mapping_ext",
        domain="future",
        priority="P0",
        table_id=708,
        source_table_name="期货.期货品种代码对照表",
        date_field="变动日",
        code_kind="future_product",
        code_pool="future_product",
        code_batch_size=500,
        postprocess="future_product",
        field_mapping={
            "StockID": "source_code",
            "stockid": "source_code",
            "品种代码": "product_code",
            "变动日": "change_date",
            "品种名称": "product_name",
            "主力代码": "main_contract_code",
            "主力代码2": "main_contract_code_2",
            "次主力代码": "secondary_main_contract_code",
            "指数线代码": "index_contract_code",
            "连续代码": "continuous_contract_code",
            "连一代码": "continuous_contract_code_1",
            "连二代码": "continuous_contract_code_2",
            "连三代码": "continuous_contract_code_3",
            "连四代码": "continuous_contract_code_4",
        },
        date_columns=("change_date",),
    )
)

FUTURE_MAIN_INFO = register_dataset(
    DatasetSpec(
        name="future_main_info",
        domain="future",
        priority="P2",
        table_id=700,
        source_table_name="期货.期货主力信息",
        frequency="daily",
        date_field="调整日期",
        code_kind="future_product",
        code_pool="future_product",
        code_batch_size=500,
        safe_query_required=True,
        postprocess="future_product",
        field_mapping={
            "StockID": "source_code",
            "stockid": "source_code",
            "品种代码": "product_code",
            "调整日期": "change_date",
            "调出日期": "out_date",
            "名称": "product_name",
            "主力代码": "main_contract_code",
            "主力月份": "main_contract_month",
        },
        date_columns=("change_date", "out_date"),
        integer_columns=("main_contract_month",),
        extra_columns=("main_virtual_code", "product_code"),
    )
)

FUTURE_TRADE_RANKING = register_dataset(
    DatasetSpec(
        name="future_trade_ranking",
        domain="future",
        priority="P2",
        table_id=701,
        source_table_name="期货.结算会员成交持仓排名",
        frequency="daily",
        date_field="截止日",
        code_kind="future",
        code_pool="future",
        code_batch_size=100,
        safe_query_required=True,
        postprocess="future",
        field_mapping={
            "StockID": "source_code",
            "stockid": "source_code",
            "代码": "contract_code_raw",
            "截止日": "trade_date",
            "排名类型": "ranking_type",
            "排名": "rank_no",
            "机构简称（标准化前）": "member_name_raw",
            "数量": "quantity",
            "比上交易日增减": "change_from_previous",
            "机构简称": "member_name",
        },
        date_columns=("trade_date",),
        numeric_columns=("quantity", "change_from_previous"),
        integer_columns=("rank_no",),
        extra_columns=("ranking_side",),
    )
)

_RANKING_TYPE_ALIASES = {
    "long": "持买单量排名",
    "buy": "持买单量排名",
    "bid": "持买单量排名",
    "多头": "持买单量排名",
    "持买单量排名": "持买单量排名",
    "short": "持卖单量排名",
    "sell": "持卖单量排名",
    "ask": "持卖单量排名",
    "空头": "持卖单量排名",
    "持卖单量排名": "持卖单量排名",
    "volume": "成交量排名",
    "vol": "成交量排名",
    "turnover": "成交量排名",
    "成交": "成交量排名",
    "成交量排名": "成交量排名",
}

_RANKING_SIDE_BY_LABEL = {
    "持买单量排名": "long",
    "持卖单量排名": "short",
    "成交量排名": "volume",
}


def _main_virtual_code(value: Any) -> str | None:
    raw = str(value or "").strip().upper()
    if not raw:
        return None
    if re.fullmatch(r"[A-Z]{1,4}", raw):
        return f"ZL{raw}10"
    return raw


def _product_from_main_virtual(value: Any) -> str | None:
    raw = str(value or "").strip().upper()
    if not raw:
        return None
    match = re.fullmatch(r"ZL([A-Z]{1,4})10", raw)
    return match.group(1) if match else raw


def _normalize_future_main_codes(codes: Any) -> list[str]:
    normalized = normalize_codes(codes, kind="future_product")
    out = [_main_virtual_code(code) for code in normalized]
    return list(dict.fromkeys(code for code in out if code))


def _main_info_query_fields(fields: Optional[Sequence[str]]) -> Optional[tuple[str, ...]]:
    if not fields:
        return None
    if isinstance(fields, (str, bytes)):
        fields = [str(fields)]
    base = ["StockID", "调整日期"]
    out: list[str] = []
    seen: set[str] = set()
    for field in (*base, *fields):
        text = str(field or "").strip()
        key = text.lower()
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return tuple(out)


def _normalize_ranking_type(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text or text.lower() == "all" or text == "全部":
        return None
    label = _RANKING_TYPE_ALIASES.get(text.lower()) or _RANKING_TYPE_ALIASES.get(text)
    if label is None:
        allowed = "all, long/buy, short/sell, volume"
        raise TinyDataParameterError(f"future_trade_ranking ranking_type must be one of {allowed}; got {value!r}.")
    return label


def _ranking_query_fields(fields: Optional[Sequence[str]]) -> Optional[tuple[str, ...]]:
    if not fields:
        return None
    if isinstance(fields, (str, bytes)):
        fields = [str(fields)]
    base = ["StockID", "代码", "截止日", "排名类型"]
    out: list[str] = []
    seen: set[str] = set()
    for field in (*base, *fields):
        text = str(field or "").strip()
        key = text.lower()
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return tuple(out)

future_basic_ext = dataset_api(FUTURE_BASIC_EXT)
future_product_mapping_ext = dataset_api(FUTURE_PRODUCT_MAPPING_EXT)


def future_main_info(
    codes=None,
    start_date=None,
    end_date=None,
    report_period=None,
    trade_date=None,
    *,
    refresh: bool = False,
    cache: bool = True,
    code_batch_size: int | None = None,
    max_workers: int | None = None,
    progress: bool | None = None,
    max_codes: int | None = None,
    fields: Optional[Sequence[str]] = None,
    all_history: bool = False,
    report_mode: int | None = None,
    as_of_date: Any = None,
) -> pd.DataFrame:
    """Fetch futures main-contract roll information from Tinysoft InfoTable 700."""

    query_codes = _normalize_future_main_codes(codes)
    if max_codes is not None:
        query_codes = query_codes[: max(1, int(max_codes))]
    if not query_codes:
        raise TinyDataParameterError("future_main_info requires product codes such as 'IF' or virtual codes such as 'ZLIF10'.")

    out = fetch_dataset(
        FUTURE_MAIN_INFO,
        codes=query_codes,
        start_date=start_date,
        end_date=end_date,
        report_period=report_period,
        trade_date=trade_date,
        refresh=refresh,
        cache=cache,
        code_batch_size=code_batch_size,
        max_workers=max_workers,
        progress=progress,
        max_codes=None,
        fields=_main_info_query_fields(fields),
        all_history=all_history,
        report_mode=report_mode,
        as_of_date=as_of_date,
    )
    if out.empty:
        return out
    out = out.copy()
    if "source_code" in out.columns:
        out["main_virtual_code"] = out["source_code"]
        out["product_code"] = out["source_code"].map(_product_from_main_virtual)
    return out


def future_trade_ranking(
    codes=None,
    start_date=None,
    end_date=None,
    trade_date=None,
    *,
    ranking_type: Any = "all",
    refresh: bool = False,
    cache: bool = True,
    code_batch_size: int | None = None,
    max_workers: int | None = None,
    progress: bool | None = None,
    max_codes: int | None = None,
    fields: Optional[Sequence[str]] = None,
    all_history: bool = False,
    as_of_date: Any = None,
) -> pd.DataFrame:
    """Fetch futures member volume/long/short ranking from Tinysoft InfoTable 701."""

    selected_type = _normalize_ranking_type(ranking_type)
    out = fetch_dataset(
        FUTURE_TRADE_RANKING,
        codes=codes,
        start_date=start_date,
        end_date=end_date,
        trade_date=trade_date,
        refresh=refresh,
        cache=cache,
        code_batch_size=code_batch_size,
        max_workers=max_workers,
        progress=progress,
        max_codes=max_codes,
        fields=_ranking_query_fields(fields),
        all_history=all_history,
        as_of_date=as_of_date,
    )
    if out.empty:
        return out
    out = out.copy()
    if "ranking_type" in out.columns:
        if selected_type is not None:
            out = out[out["ranking_type"].astype("string") == selected_type].copy()
        out["ranking_side"] = out["ranking_type"].map(_RANKING_SIDE_BY_LABEL)
    return out.reset_index(drop=True)

__all__ = [
    "FUTURE_BASIC_EXT",
    "FUTURE_MAIN_INFO",
    "FUTURE_PRODUCT_MAPPING_EXT",
    "FUTURE_TRADE_RANKING",
    "future_basic_ext",
    "future_main_info",
    "future_product_mapping_ext",
    "future_trade_ranking",
]

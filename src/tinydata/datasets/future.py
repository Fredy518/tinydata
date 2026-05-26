"""Futures dataset APIs."""

from __future__ import annotations

from .specs import DatasetSpec, dataset_api, register_dataset


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

future_basic_ext = dataset_api(FUTURE_BASIC_EXT)
future_product_mapping_ext = dataset_api(FUTURE_PRODUCT_MAPPING_EXT)

__all__ = [
    "FUTURE_BASIC_EXT",
    "FUTURE_PRODUCT_MAPPING_EXT",
    "future_basic_ext",
    "future_product_mapping_ext",
]

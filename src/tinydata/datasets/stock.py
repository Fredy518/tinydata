"""Stock dataset APIs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional, Sequence

import pandas as pd

from ..cache import CacheManager, make_cache_key
from ..client import TinyClient
from ..codes import normalize_codes
from ..errors import TinyDataParameterError
from ..infotable import parse_tinysoft_date, quote_tsl_string
from ..parallel import run_parallel_code_queries
from .specs import DatasetSpec, dataset_api, process_dataset_frame, register_dataset


logger = logging.getLogger(__name__)


def _stock_spec(
    name: str,
    table_id: int,
    source_table_name: str,
    field_mapping: dict[str, str],
    *,
    priority: str = "P0",
    date_field: str | None = None,
    code_kind: str | None = "stock",
    code_batch_size: int = 500,
    safe_query_required: bool = True,
    source_kind: str = "infotable",
    date_columns: tuple[str, ...] = (),
    numeric_columns: tuple[str, ...] = (),
    integer_columns: tuple[str, ...] = (),
    postprocess: str | None = None,
    extra_columns: tuple[str, ...] = (),
) -> DatasetSpec:
    return register_dataset(
        DatasetSpec(
            name=name,
            domain="stock",
            priority=priority,
            source_kind=source_kind,
            table_id=table_id,
            source_table_name=source_table_name,
            field_mapping=field_mapping,
            date_field=date_field,
            code_kind=code_kind,
            code_pool=code_kind,
            code_batch_size=code_batch_size,
            safe_query_required=safe_query_required,
            date_columns=date_columns,
            numeric_columns=numeric_columns,
            integer_columns=integer_columns,
            postprocess=postprocess,
            extra_columns=extra_columns,
        )
    )


STOCK_BASIC_EXT = _stock_spec(
    "stock_basic_ext",
    10,
    "股票.基本信息",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "A股代码": "a_share_code",
        "公司中文全称": "company_full_name",
        "公司中文简称": "company_short_name",
        "B股代码": "b_share_code",
        "B股简称": "b_share_short_name",
        "公司英文全称": "company_full_name_en",
        "公司英文简称": "company_short_name_en",
        "注册资本": "registered_capital",
        "法定代表人": "legal_representative",
        "成立日期": "establish_date",
        "公司注册地址": "registered_address",
        "经营范围": "business_scope",
        "主营业务": "main_business",
        "地域": "area",
        "股票种类": "stock_type",
        "当前状态": "current_status",
        "上市地": "list_location",
        "所属市场": "market",
        "申万一级行业": "sw_industry_l1",
        "申万二级行业": "sw_industry_l2",
        "申万三级行业": "sw_industry_l3",
        "申万一级行业代码": "sw_industry_l1_code",
        "申万二级行业代码": "sw_industry_l2_code",
        "申万三级行业代码": "sw_industry_l3_code",
        "中证一级行业": "csi_industry_l1",
        "中证二级行业": "csi_industry_l2",
        "中证三级行业": "csi_industry_l3",
        "中证四级行业": "csi_industry_l4",
        "证监会一级行业名称": "csrc_industry_l1",
        "证监会二级行业名称": "csrc_industry_l2",
        "H股代码": "h_share_code",
        "H股简称": "h_share_short_name",
        "股本单位": "capital_unit",
        "转换比例": "capital_conversion_ratio",
    },
    code_batch_size=2000,
    safe_query_required=False,
    date_columns=("establish_date",),
    numeric_columns=("registered_capital", "capital_conversion_ratio"),
)

STOCK_IPO = _stock_spec(
    "stock_ipo",
    12,
    "股票.发行上市",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "stock_name",
        "证券代码": "tsl_code",
        "股票种类": "stock_type",
        "每股面值": "par_value",
        "发行额度": "issue_quota",
        "占发行总股本比例(%)": "issue_total_share_ratio_pct",
        "发行后总股本": "total_share_after_issue",
        "发行价": "issue_price",
        "上市地": "list_location",
        "发行市盈率": "issue_pe",
        "发行后市盈率": "pe_after_issue",
        "发行前每股净资产": "bps_before_issue",
        "发行后每股净资产": "bps_after_issue",
        "市净率": "pb",
        "发行后全面摊薄每股收益": "eps_diluted_after_issue",
        "发行对象": "issue_target",
        "发行方式": "issue_method",
        "网下向询价对象配售股数": "offline_placing_share",
        "网上向社会公众投资者发行股数": "online_issue_share",
        "战略投资者配售股数": "strategic_investor_placing_share",
        "老股东转让股数": "old_shareholder_transfer_share",
        "承销方式": "underwriting_method",
        "招股意向书公布日": "prospectus_intent_ann_date",
        "初步询价开始日": "bookbuilding_start_date",
        "初步询价截止日": "bookbuilding_end_date",
        "价格区间确定日": "price_range_date",
        "发行起始日": "issue_start_date",
        "发行截止日": "issue_end_date",
        "网上申购日": "online_subscription_date",
        "发行价格确定日": "issue_price_date",
        "网上申购配号日": "online_lottery_number_date",
        "定价公告公布日": "pricing_ann_date",
        "网下发行结果公告日": "offline_result_ann_date",
        "网上发行结果公告日": "online_result_ann_date",
        "招股说明书签署日": "prospectus_sign_date",
        "上市日": "list_date",
        "募集资金": "raise_amount",
        "募集资金净额": "raise_net_amount",
        "发行费用": "issue_expense",
        "承销保荐费用": "underwriting_sponsor_fee",
        "审计费用": "audit_fee",
        "评估费用": "valuation_fee",
        "律师费用": "legal_fee",
        "路演推介费": "roadshow_fee",
        "发行手续费用": "issue_handling_fee",
        "印花税": "stamp_tax",
        "每股发行费用": "issue_expense_per_share",
        "主承销商": "lead_underwriter",
        "发行人律师": "issuer_lawyer",
        "主承销商律师": "underwriter_lawyer",
        "会计师事务所": "accounting_firm",
        "资产评估机构": "asset_appraisal_agency",
        "土地评估机构": "land_appraisal_agency",
        "股票登记机构": "stock_registration_agency",
        "募集资金用途": "raise_fund_usage",
        "网下询价对象家数": "offline_inquiry_investor_count",
        "网下配售家数": "offline_placing_investor_count",
        "网下符合要求家数": "offline_valid_investor_count",
        "网下冻结资金总额": "offline_frozen_amount",
        "网下有效申购总量": "offline_valid_subscription_share",
        "网下有效申购资金总额": "offline_valid_subscription_amount",
        "网下初步配售比例(%)": "offline_initial_placing_ratio_pct",
        "网下最终配售比例(%)": "offline_final_placing_ratio_pct",
        "网下初步认购倍数": "offline_initial_subscription_multiple",
        "网下最终认购倍数": "offline_final_subscription_multiple",
        "网下配售对象锁定期(月)": "offline_lockup_months",
        "网上发行有效申购户数": "online_valid_account_count",
        "网上发行有效申购股数": "online_valid_subscription_share",
        "网上初步中签率(%)": "online_initial_lottery_ratio_pct",
        "网上最终中签率(%)": "online_final_lottery_ratio_pct",
        "一级行业名称": "industry_l1",
        "二级行业名称": "industry_l2",
        "三级行业名称": "industry_l3",
        "申购代码": "subscription_code",
        "新三板挂牌日": "neeq_list_date",
    },
    priority="P1",
    date_field="上市日",
    code_batch_size=1000,
    safe_query_required=False,
    date_columns=(
        "prospectus_intent_ann_date",
        "bookbuilding_start_date",
        "bookbuilding_end_date",
        "price_range_date",
        "issue_start_date",
        "issue_end_date",
        "online_subscription_date",
        "issue_price_date",
        "online_lottery_number_date",
        "pricing_ann_date",
        "offline_result_ann_date",
        "online_result_ann_date",
        "prospectus_sign_date",
        "list_date",
        "neeq_list_date",
    ),
    numeric_columns=(
        "par_value",
        "issue_quota",
        "issue_total_share_ratio_pct",
        "total_share_after_issue",
        "issue_price",
        "issue_pe",
        "pe_after_issue",
        "bps_before_issue",
        "bps_after_issue",
        "pb",
        "eps_diluted_after_issue",
        "offline_placing_share",
        "online_issue_share",
        "strategic_investor_placing_share",
        "old_shareholder_transfer_share",
        "raise_amount",
        "raise_net_amount",
        "issue_expense",
        "underwriting_sponsor_fee",
        "audit_fee",
        "valuation_fee",
        "legal_fee",
        "roadshow_fee",
        "issue_handling_fee",
        "stamp_tax",
        "issue_expense_per_share",
        "offline_inquiry_investor_count",
        "offline_placing_investor_count",
        "offline_valid_investor_count",
        "offline_frozen_amount",
        "offline_valid_subscription_share",
        "offline_valid_subscription_amount",
        "offline_initial_placing_ratio_pct",
        "offline_final_placing_ratio_pct",
        "offline_initial_subscription_multiple",
        "offline_final_subscription_multiple",
        "offline_lockup_months",
        "online_valid_account_count",
        "online_valid_subscription_share",
        "online_initial_lottery_ratio_pct",
        "online_final_lottery_ratio_pct",
    ),
)

STOCK_DELIST_SOLUTION = _stock_spec(
    "stock_delist_solution",
    17,
    "股票.终止上市股份处理方案",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "stock_name",
        "证券代码": "tsl_code",
        "截止日": "trade_date",
        "股份处理方式": "share_treatment",
        "换股后代码": "swap_code_raw",
        "换股比例": "swap_ratio",
        "现金对价": "cash_consideration",
    },
    priority="P2",
    date_field="截止日",
    code_batch_size=500,
    safe_query_required=True,
    date_columns=("trade_date",),
    numeric_columns=("swap_ratio", "cash_consideration"),
)

STOCK_SUSPEND = _stock_spec(
    "stock_suspend",
    127,
    "股票.特别提示-停牌",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "停牌开始日": "suspend_start_date",
        "停牌开始时间": "suspend_start_time",
        "停牌截止日": "suspend_end_date",
        "停牌截止时间": "suspend_end_time",
        "停牌期限": "suspend_term",
        "停牌原因": "suspend_reason",
    },
    date_field="停牌开始日",
    code_batch_size=200,
    date_columns=("suspend_start_date", "suspend_end_date", "trade_date"),
    postprocess="stock_suspend",
    extra_columns=("trade_date", "event_type", "event_text"),
)

STOCK_INDUSTRY_VERSIONED = _stock_spec(
    "stock_industry_versioned",
    139,
    "股票.股票行业分类",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "属性代码": "attr_code",
        "属性名称": "attr_name",
        "级数": "level_no",
        "入选日期": "in_date",
        "剔除日期": "out_date",
        "最新标识": "is_latest",
        "所属属性代码": "root_attr_code",
        "所属属性名称": "root_attr_name",
    },
    code_batch_size=200,
    date_columns=("in_date", "out_date", "trade_date"),
    numeric_columns=("level_no", "is_latest"),
    integer_columns=("level_no", "is_latest"),
    postprocess="stock_industry",
    extra_columns=("trade_date", "industry_source", "industry_l1", "industry_l2", "industry_l3", "industry_code", "source_name"),
)

STOCK_CLASSIFICATION_INFO = _stock_spec(
    "stock_classification_info",
    138,
    "股票.股票行业分类信息",
    {
        "StockID": "attr_request_code",
        "stockid": "attr_request_code",
        "属性代码": "attr_code",
        "属性名称": "attr_name",
        "级数": "level_no",
        "上级属性代码": "parent_attr_code",
        "上级属性名称": "parent_attr_name",
        "入选日期": "in_date",
        "剔除日期": "out_date",
        "最新标识": "is_latest",
        "所属属性代码": "root_attr_code",
    },
    priority="P1",
    code_kind=None,
    code_batch_size=500,
    safe_query_required=True,
    date_columns=("in_date", "out_date"),
    numeric_columns=("level_no", "is_latest"),
    integer_columns=("level_no", "is_latest"),
)

STOCK_FINA_PIT_EXT = _stock_spec(
    "stock_fina_pit_ext",
    42,
    "股票.主要财务指标",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "截止日": "report_date",
        "公布日": "ann_date",
        "每股收益(摊薄)": "metric_eps_diluted",
        "每股净资产": "metric_bps",
        "净资产收益率(摊薄)(%)": "metric_roe_diluted",
        "扣除非经常性损益后的净利润": "metric_netprofit_excl_nr",
    },
    date_field="公布日",
    code_batch_size=120,
    date_columns=("report_date", "ann_date", "trade_date"),
    numeric_columns=("metric_eps_diluted", "metric_bps", "metric_roe_diluted", "metric_netprofit_excl_nr", "metric_value"),
    integer_columns=("metric_field_id",),
    postprocess="stock_fina_pit",
    extra_columns=("trade_date", "report_date", "ann_date", "finance_source", "metric_name", "metric_expr", "metric_field_id", "metric_value", "metric_text"),
)


@dataclass(frozen=True)
class _ValuationMetric:
    field_id: int
    source_name: str
    column: str
    function_name: str
    description: str


_VALUATION_METRICS: tuple[_ValuationMetric, ...] = (
    _ValuationMetric(9901100, "EBIT", "ebit", "EBIT_", "息税前利润"),
    _ValuationMetric(9901101, "EBITDA", "ebitda", "EBITDA_", "息税折旧摊销前利润"),
    _ValuationMetric(9901102, "NOPLAT", "noplat", "NOPLAT_", "息前税后利润"),
    _ValuationMetric(9901103, "EV", "ev", "EV", "企业价值"),
    _ValuationMetric(9901104, "付息债务", "interest_bearing_debt", "DebtWithInterest", "付息债务"),
    _ValuationMetric(9901105, "净债务", "net_debt", "NetDebt", "净债务"),
    _ValuationMetric(9901106, "IC", "ic", "ValueInSheetAdjust", "资本账面价值"),
    _ValuationMetric(9901107, "资本性投资", "capital_investment", "CashPaidtoInvestments", "资本性投资"),
    _ValuationMetric(9901108, "EBIT/营业收入", "ebit_to_revenue", "EBITvsMainIncome_", "EBIT/营业收入"),
    _ValuationMetric(9901109, "EBITDA/营业收入", "ebitda_to_revenue", "EBIDAvsMainIncome_", "EBITDA/营业收入"),
    _ValuationMetric(9901110, "EV/营业收入", "ev_to_revenue", "EvvsMainIncome", "EV/营业收入"),
    _ValuationMetric(9901111, "EV/EBIT", "ev_to_ebit", "EVvsEBIT_", "EV/EBIT"),
    _ValuationMetric(9901112, "EV/EBITDA", "ev_to_ebitda", "EVvsEBITDA_", "EV/EBITDA"),
    _ValuationMetric(9901113, "EV/NOPLAT", "ev_to_noplat", "EVvsNOPLAT_", "EV/NOPLAT"),
    _ValuationMetric(9901114, "EV/IC", "ev_to_ic", "EvvsIC", "EV/IC"),
    _ValuationMetric(9901115, "ROIC", "roic_pct", "ROIC", "NOPLAT/IC*100%"),
    _ValuationMetric(9901116, "新增折旧与摊销", "added_da", "AddedDA", "新增折旧与摊销"),
    _ValuationMetric(9901117, "追加营运资本", "added_working_capital", "AddedWorkingCapital", "追加营运资本"),
    _ValuationMetric(9901118, "新增资本性支出", "capex", "Capex", "新增资本性支出"),
    _ValuationMetric(9901119, "自由现金流(FCFF)", "fcff", "FCFF", "自由现金流(FCFF)"),
    _ValuationMetric(9901120, "每股自由现金流", "fcff_per_share", "FCFFPS", "每股自由现金流"),
    _ValuationMetric(9901121, "非核心资产价值", "non_core_asset_value", "ValueOfFHX", "非核心资产价值"),
    _ValuationMetric(9901122, "有形资本", "tangible_capital", "TangibleCapital", "有形资本"),
    _ValuationMetric(9901123, "有形资本回报率(%)", "rotc_pct", "ROTC", "有形资本回报率(%)"),
)

_VALUATION_IDENTIFIER_FIELDS = {
    "request_code",
    "source_table_id",
    "source_table_name",
    "ts_code",
    "tsl_code",
    "report_date",
    "截止日",
    "StockID",
    "stockid",
    "证券代码",
}


@dataclass(frozen=True)
class _FinanceFunctionMetric:
    field_id: int
    source_name: str
    column: str
    function_name: str
    description: str


_TTM_METRICS: tuple[_FinanceFunctionMetric, ...] = (
    _FinanceFunctionMetric(46080, "营业总收入", "total_revenue_ttm", "total_revenue", "利润表累计流量项"),
    _FinanceFunctionMetric(46002, "营业收入", "revenue_ttm", "revenue", "利润表累计流量项"),
    _FinanceFunctionMetric(46005, "营业成本", "operating_cost_ttm", "operating_cost", "利润表累计流量项"),
    _FinanceFunctionMetric(46015, "营业利润", "operate_profit_ttm", "operate_profit", "利润表累计流量项"),
    _FinanceFunctionMetric(46024, "利润总额", "total_profit_ttm", "total_profit", "利润表累计流量项"),
    _FinanceFunctionMetric(46033, "净利润", "net_profit_ttm", "net_profit", "利润表累计流量项"),
    _FinanceFunctionMetric(
        46078,
        "归属于母公司所有者净利润",
        "parent_net_profit_ttm",
        "parent_net_profit",
        "利润表累计流量项",
    ),
    _FinanceFunctionMetric(
        48018,
        "经营活动产生的现金流量净额",
        "net_operating_cashflow_ttm",
        "net_operating_cashflow",
        "现金流量表累计流量项",
    ),
    _FinanceFunctionMetric(
        48030,
        "购建固定资产、无形资产和其他长期资产所支付的现金",
        "cash_paid_for_fixed_intangible_assets_ttm",
        "cash_paid_for_fixed_intangible_assets",
        "现金流量表累计流量项",
    ),
    _FinanceFunctionMetric(
        48039,
        "投资活动产生的现金流量净额",
        "net_investing_cashflow_ttm",
        "net_investing_cashflow",
        "现金流量表累计流量项",
    ),
    _FinanceFunctionMetric(
        48056,
        "筹资活动产生的现金流量净额",
        "net_financing_cashflow_ttm",
        "net_financing_cashflow",
        "现金流量表累计流量项",
    ),
)

_FINANCE_FUNCTION_IDENTIFIER_FIELDS = {
    "request_code",
    "source_table_id",
    "source_table_name",
    "ts_code",
    "tsl_code",
    "report_date",
    "as_of_date",
    "截止日",
    "取数日",
    "StockID",
    "stockid",
    "证券代码",
}


def _valuation_aliases(metric: _ValuationMetric) -> tuple[str, ...]:
    return (
        metric.source_name,
        metric.column,
        metric.function_name,
        str(metric.field_id),
    )


def _select_valuation_metrics(fields: Optional[Sequence[str]]) -> tuple[_ValuationMetric, ...]:
    if not fields:
        return _VALUATION_METRICS
    if isinstance(fields, (str, bytes)):
        fields = [str(fields)]

    aliases: dict[str, _ValuationMetric] = {}
    for metric in _VALUATION_METRICS:
        for alias in _valuation_aliases(metric):
            aliases[str(alias).strip().lower()] = metric
    identifier_fields = {field.lower() for field in _VALUATION_IDENTIFIER_FIELDS}

    selected: list[_ValuationMetric] = []
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
        allowed = ", ".join(metric.column for metric in _VALUATION_METRICS)
        raise TinyDataParameterError(
            "stock_valuation_indicator fields must be valuation metric names, mapped columns, or ReportOfAll field ids. "
            f"Unknown: {unknown}. Allowed mapped columns: {allowed}."
        )
    if not selected:
        raise TinyDataParameterError("stock_valuation_indicator fields must include at least one valuation metric.")
    return tuple(selected)


def _finance_function_aliases(metric: _FinanceFunctionMetric) -> tuple[str, ...]:
    return (
        metric.source_name,
        metric.column,
        metric.function_name,
        str(metric.field_id),
    )


def _select_finance_function_metrics(
    fields: Optional[Sequence[str]],
    *,
    metrics: Sequence[_FinanceFunctionMetric],
    dataset_name: str,
    allowed_message: str,
) -> tuple[_FinanceFunctionMetric, ...]:
    if not fields:
        return tuple(metrics)
    if isinstance(fields, (str, bytes)):
        fields = [str(fields)]

    aliases: dict[str, _FinanceFunctionMetric] = {}
    for metric in metrics:
        for alias in _finance_function_aliases(metric):
            aliases[str(alias).strip().lower()] = metric
    identifier_fields = {field.lower() for field in _FINANCE_FUNCTION_IDENTIFIER_FIELDS}

    selected: list[_FinanceFunctionMetric] = []
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
        allowed = ", ".join(metric.column for metric in metrics)
        raise TinyDataParameterError(
            f"{dataset_name} fields {allowed_message}. Unknown: {unknown}. Allowed mapped columns: {allowed}."
        )
    if not selected:
        raise TinyDataParameterError(f"{dataset_name} fields must include at least one metric.")
    return tuple(selected)


STOCK_VALUATION_INDICATOR = _stock_spec(
    "stock_valuation_indicator",
    0,
    "股票.估值指标",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "截止日": "report_date",
        **{metric.source_name: metric.column for metric in _VALUATION_METRICS},
    },
    priority="P1",
    source_kind="tsl_function",
    code_batch_size=1,
    safe_query_required=True,
    date_columns=("report_date",),
    numeric_columns=tuple(metric.column for metric in _VALUATION_METRICS),
)

STOCK_TTM_INDICATOR = _stock_spec(
    "stock_ttm_indicator",
    0,
    "股票.TTM财务指标",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "截止日": "report_date",
        "取数日": "as_of_date",
        **{metric.source_name: metric.column for metric in _TTM_METRICS},
    },
    priority="P1",
    source_kind="tsl_function",
    code_batch_size=1,
    safe_query_required=True,
    date_columns=("report_date", "as_of_date"),
    numeric_columns=tuple(metric.column for metric in _TTM_METRICS),
)


def _format_reportofall_period(report_period: Any) -> str:
    if report_period in (None, ""):
        raise TinyDataParameterError("stock_valuation_indicator requires report_period.")
    dt = parse_tinysoft_date(report_period)
    if pd.isna(dt):
        raise TinyDataParameterError(f"Invalid report_period for stock_valuation_indicator: {report_period!r}.")
    return dt.strftime("%Y%m%d")


def _format_finance_function_period(dataset_name: str, report_period: Any) -> str:
    if report_period in (None, ""):
        raise TinyDataParameterError(f"{dataset_name} requires report_period.")
    dt = parse_tinysoft_date(report_period)
    if pd.isna(dt):
        raise TinyDataParameterError(f"Invalid report_period for {dataset_name}: {report_period!r}.")
    return dt.strftime("%Y%m%d")


def _format_optional_as_of_date(dataset_name: str, as_of_date: Any) -> str | None:
    if as_of_date in (None, ""):
        return None
    dt = parse_tinysoft_date(as_of_date)
    if pd.isna(dt):
        raise TinyDataParameterError(f"Invalid as_of_date for {dataset_name}: {as_of_date!r}.")
    return dt.strftime("%Y%m%d")


def _build_valuation_cache_key(
    spec: DatasetSpec,
    codes: Sequence[str],
    report_period: str,
    metrics: Sequence[_ValuationMetric],
) -> str:
    return make_cache_key(
        spec.name,
        {
            "codes": list(codes),
            "report_period": report_period,
            "field_ids": [metric.field_id for metric in metrics],
            "field_version": spec.field_version,
        },
    )


def _build_finance_function_cache_key(
    spec: DatasetSpec,
    codes: Sequence[str],
    report_period: str,
    as_of_date: str | None,
    metrics: Sequence[_FinanceFunctionMetric],
    extra: dict[str, Any] | None = None,
) -> str:
    payload: dict[str, Any] = {
        "codes": list(codes),
        "report_period": report_period,
        "as_of_date": as_of_date,
        "field_ids": [metric.field_id for metric in metrics],
        "field_version": spec.field_version,
    }
    if extra:
        payload.update(extra)
    return make_cache_key(spec.name, payload)


def _build_reportofall_tsl(code: str, report_period: str, metrics: Sequence[_ValuationMetric]) -> str:
    calls = ",".join(f"ReportOfAll({metric.field_id},{report_period})" for metric in metrics)
    return f"setsysparam(pn_stock(),{quote_tsl_string(code)});return array({calls});"


def _build_ttm_tsl(
    code: str,
    report_period: str,
    as_of_date: str | None,
    metrics: Sequence[_FinanceFunctionMetric],
) -> str:
    calls = ",".join(f"Last12MData({report_period},{metric.field_id})" for metric in metrics)
    statements = [f"setsysparam(pn_stock(),{quote_tsl_string(code)})"]
    if as_of_date is not None:
        statements.append(f"setsysparam(pn_date(),{as_of_date}T)")
    statements.append(f"return array({calls})")
    return ";".join(statements) + ";"


def _payload_values(payload: Any) -> list[Any]:
    if payload is None:
        return []
    if isinstance(payload, pd.DataFrame):
        if payload.empty:
            return []
        if len(payload.columns) == 1:
            return payload.iloc[:, 0].tolist()
        return payload.iloc[0].tolist()
    if isinstance(payload, list):
        out: list[Any] = []
        for item in payload:
            if isinstance(item, dict):
                for key in ("value", "Value", "data", "Data"):
                    if key in item:
                        out.append(item[key])
                        break
                else:
                    out.append(item)
            else:
                out.append(item)
        return out
    if isinstance(payload, dict):
        for key in ("data", "Data", "value", "Value"):
            if key in payload:
                value = payload[key]
                return _payload_values(value) if isinstance(value, (list, pd.DataFrame)) else [value]
        return [payload]
    return [payload]


def stock_valuation_indicator(
    codes=None,
    report_period=None,
    *,
    fields: Optional[Sequence[str]] = None,
    refresh: bool = False,
    cache: bool = True,
    max_workers: int | None = None,
    progress: bool | None = None,
    max_codes=None,
) -> pd.DataFrame:
    """Fetch Tinysoft stock valuation indicators through ``ReportOfAll``."""

    period_literal = _format_reportofall_period(report_period)
    normalized = normalize_codes(codes, kind="stock")
    if not normalized:
        raise TinyDataParameterError("stock_valuation_indicator requires one or more stock codes.")
    if max_codes is not None:
        normalized = normalized[: max(1, int(max_codes))]

    metrics = _select_valuation_metrics(fields)
    manager = CacheManager()
    key = _build_valuation_cache_key(STOCK_VALUATION_INDICATOR, normalized, period_literal, metrics)
    if cache and not refresh:
        cached = manager.read(STOCK_VALUATION_INDICATOR.name, key)
        if cached is not None:
            return cached

    client = TinyClient()

    def fetch_one(code: str) -> pd.DataFrame | None:
        raw_values = _payload_values(client.exec(_build_reportofall_tsl(code, period_literal, metrics), as_dataframe=False))
        row = {"StockID": code, "截止日": period_literal}
        for idx, metric in enumerate(metrics):
            row[metric.source_name] = raw_values[idx] if idx < len(raw_values) else None
        processed = process_dataset_frame(pd.DataFrame([row]), STOCK_VALUATION_INDICATOR)
        if fields:
            keep = {"request_code", "source_table_id", "source_table_name", "ts_code", "tsl_code", "report_date"}
            keep.update(metric.column for metric in metrics)
            processed = processed[[col for col in processed.columns if col in keep]]
        return processed

    frames = [
        frame
        for frame in run_parallel_code_queries(
            normalized,
            fetch_one=fetch_one,
            max_workers=max_workers,
            progress=progress,
            description=f"{STOCK_VALUATION_INDICATOR.name} codes",
            logger=logger,
            rate_limit_scope=f"parallel {STOCK_VALUATION_INDICATOR.name} queries",
        )
        if not frame.empty
    ]

    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if cache:
        manager.write(STOCK_VALUATION_INDICATOR.name, key, out)
    return out


def stock_ttm_indicator(
    codes=None,
    report_period=None,
    *,
    as_of_date=None,
    fields: Optional[Sequence[str]] = None,
    refresh: bool = False,
    cache: bool = True,
    max_workers: int | None = None,
    progress: bool | None = None,
    max_codes=None,
) -> pd.DataFrame:
    """Fetch whitelisted Tinysoft TTM finance indicators through ``Last12MData``."""

    period_literal = _format_finance_function_period(STOCK_TTM_INDICATOR.name, report_period)
    as_of_literal = _format_optional_as_of_date(STOCK_TTM_INDICATOR.name, as_of_date)
    normalized = normalize_codes(codes, kind="stock")
    if not normalized:
        raise TinyDataParameterError("stock_ttm_indicator requires one or more stock codes.")
    if max_codes is not None:
        normalized = normalized[: max(1, int(max_codes))]

    metrics = _select_finance_function_metrics(
        fields,
        metrics=_TTM_METRICS,
        dataset_name=STOCK_TTM_INDICATOR.name,
        allowed_message=(
            "must be whitelisted Last12MData metric names, mapped columns, or field ids; "
            "balance-sheet point-in-time items are intentionally excluded"
        ),
    )
    manager = CacheManager()
    key = _build_finance_function_cache_key(
        STOCK_TTM_INDICATOR,
        normalized,
        period_literal,
        as_of_literal,
        metrics,
    )
    if cache and not refresh:
        cached = manager.read(STOCK_TTM_INDICATOR.name, key)
        if cached is not None:
            return cached

    client = TinyClient()

    def fetch_one(code: str) -> pd.DataFrame | None:
        tsl = _build_ttm_tsl(
            code,
            period_literal,
            as_of_literal,
            metrics,
        )
        raw_values = _payload_values(client.exec(tsl, as_dataframe=False))
        row = {"StockID": code, "截止日": period_literal, "取数日": as_of_literal}
        for idx, metric in enumerate(metrics):
            row[metric.source_name] = raw_values[idx] if idx < len(raw_values) else None
        processed = process_dataset_frame(pd.DataFrame([row]), STOCK_TTM_INDICATOR)
        if fields:
            keep = {
                "request_code",
                "source_table_id",
                "source_table_name",
                "ts_code",
                "tsl_code",
                "report_date",
                "as_of_date",
            }
            keep.update(metric.column for metric in metrics)
            processed = processed[[col for col in processed.columns if col in keep]]
        return processed

    frames = [
        frame
        for frame in run_parallel_code_queries(
            normalized,
            fetch_one=fetch_one,
            max_workers=max_workers,
            progress=progress,
            description=f"{STOCK_TTM_INDICATOR.name} codes",
            logger=logger,
            rate_limit_scope=f"parallel {STOCK_TTM_INDICATOR.name} queries",
        )
        if not frame.empty
    ]

    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if cache:
        manager.write(STOCK_TTM_INDICATOR.name, key, out)
    return out


FINA_INDICATOR = _stock_spec(
    "fina_indicator",
    42,
    "股票.主要财务指标",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "截止日": "report_date",
        "公布日": "ann_date",
        "每股收益(摊薄)": "eps_diluted",
        "每股收益(加权)": "eps_weighted",
        "每股收益(扣除,摊薄)": "eps_excl_nr_diluted",
        "每股收益(扣除,加权)": "eps_excl_nr_weighted",
        "每股净资产": "bps",
        "每股净资产(调整)": "bps_adjusted",
        "每股经营活动现金流量净额": "ocfps",
        "每股资本公积金": "capital_reserve_per_share",
        "每股未分配利润": "undistributed_profit_per_share",
        "每股现金净流量": "net_cashflow_per_share",
        "净资产收益率(摊薄)(%)": "roe_diluted_pct",
        "净资产收益率(加权)(%)": "roe_weighted_pct",
        "净资产收益率(调整)(%)": "roe_adjusted_pct",
        "净资产收益率(扣除,摊薄)(%)": "roe_excl_nr_diluted_pct",
        "净资产收益率(扣除,加权)(%)": "roe_excl_nr_weighted_pct",
        "扣除非经常性损益后的净利润": "netprofit_excl_nr",
        "备注": "remark",
        "报告类型": "report_type",
    },
    date_field="公布日",
    code_batch_size=160,
    safe_query_required=True,
    date_columns=("report_date", "ann_date"),
    numeric_columns=(
        "eps_diluted",
        "eps_weighted",
        "eps_excl_nr_diluted",
        "eps_excl_nr_weighted",
        "bps",
        "bps_adjusted",
        "ocfps",
        "capital_reserve_per_share",
        "undistributed_profit_per_share",
        "net_cashflow_per_share",
        "roe_diluted_pct",
        "roe_weighted_pct",
        "roe_adjusted_pct",
        "roe_excl_nr_diluted_pct",
        "roe_excl_nr_weighted_pct",
        "netprofit_excl_nr",
    ),
)

FINA_BALANCESHEET = _stock_spec(
    "fina_balancesheet",
    44,
    "股票.合并资产负债表",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "截止日": "report_date",
        "数据报告期": "data_report_period",
        "公布日": "ann_date",
        "会计准则": "accounting_standard",
        "货币资金": "money_cap",
        "交易性金融资产": "tradable_fin_assets",
        "应收票据及应收账款": "notes_and_accounts_receivable",
        "应收票据": "notes_receivable",
        "应收帐款": "accounts_receivable",
        "应收款项融资": "receivables_financing",
        "预付帐款": "prepayment",
        "其他应收款": "other_receivables",
        "存货": "inventories",
        "合同资产": "contract_assets",
        "其他流动资产": "other_current_assets",
        "流动资产合计": "total_current_assets",
        "债权投资": "debt_investment",
        "其他债权投资": "other_debt_investment",
        "其他权益工具投资": "other_equity_investment",
        "长期股权投资": "long_term_equity_investment",
        "投资性房地产": "investment_property",
        "固定资产净额": "fixed_assets_net",
        "在建工程": "construction_in_progress",
        "无形资产": "intangible_assets",
        "商誉": "goodwill",
        "递延税款借项": "deferred_tax_assets_legacy",
        "非流动资产合计": "total_non_current_assets",
        "资产总计": "total_assets",
        "短期借款": "short_term_loans",
        "应付票据及应付账款": "notes_and_accounts_payable",
        "应付票据": "notes_payable",
        "应付帐款": "accounts_payable",
        "预收帐款": "advance_receipts",
        "合同负债": "contract_liabilities",
        "应付职工薪酬": "payroll_payable",
        "应付股利": "dividend_payable",
        "应交税金": "taxes_payable",
        "其他应付款": "other_payables",
        "流动负债合计": "total_current_liabilities",
        "长期借款": "long_term_loans",
        "应付债券": "bonds_payable",
        "租赁负债": "lease_liabilities",
        "长期应付款": "long_term_payables",
        "长期负债合计": "total_non_current_liabilities",
        "负债合计": "total_liabilities",
        "少数股东权益": "minority_interests",
        "股本": "share_capital",
        "资本公积": "capital_reserve",
        "减：库存股": "treasury_stock",
        "其他综合收益": "other_comprehensive_income",
        "盈余公积": "surplus_reserve",
        "未分配利润": "undistributed_profit",
        "归属母公司股东权益合计": "total_parent_equity",
        "股东权益合计": "total_equity",
        "负债与股东权益总计": "total_liabilities_and_equity",
        "备注": "remark",
        "报告类型": "report_type",
    },
    date_field="公布日",
    code_batch_size=120,
    safe_query_required=True,
    date_columns=("report_date", "data_report_period", "ann_date"),
)

FINA_INCOME = _stock_spec(
    "fina_income",
    46,
    "股票.合并利润分配表",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "截止日": "report_date",
        "数据报告期": "data_report_period",
        "公布日": "ann_date",
        "会计准则": "accounting_standard",
        "营业总收入": "total_revenue",
        "营业收入": "revenue",
        "利息收入": "interest_income",
        "营业总成本": "total_operating_cost",
        "营业成本": "operating_cost",
        "营业税金及附加": "taxes_and_surcharges",
        "营业费用": "selling_expense",
        "管理费用": "admin_expense",
        "财务费用": "finance_expense",
        "研发费用": "rd_expense",
        "资产减值损失": "asset_impairment_loss",
        "信用减值损失": "credit_impairment_loss",
        "公允价值变动净收益": "fair_value_change_income",
        "投资收益": "invest_income",
        "其中：对联营合营企业投资收益": "associate_jv_invest_income",
        "其他收益": "other_income",
        "资产处置收益": "asset_disposal_income",
        "营业利润": "operate_profit",
        "营业外收入": "non_operating_income",
        "营业外支出": "non_operating_expense",
        "利润总额": "total_profit",
        "所得税": "income_tax",
        "净利润": "net_profit",
        "少数股东损益": "minority_profit",
        "归属于母公司所有者净利润": "parent_net_profit",
        "持续经营净利润": "continued_net_profit",
        "终止经营净利润": "discontinued_net_profit",
        "其他综合收益的税后净额": "other_comprehensive_income_after_tax",
        "综合收益总额": "total_comprehensive_income",
        "归属于母公司所有者的综合收益总额": "parent_total_comprehensive_income",
        "基本每股收益": "basic_eps",
        "稀释每股收益": "diluted_eps",
        "未分配利润": "undistributed_profit",
        "备注": "remark",
        "报告类型": "report_type",
    },
    date_field="公布日",
    code_batch_size=120,
    safe_query_required=True,
    date_columns=("report_date", "data_report_period", "ann_date"),
)

FINA_CASHFLOW = _stock_spec(
    "fina_cashflow",
    48,
    "股票.合并现金流量表",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "截止日": "report_date",
        "数据报告期": "data_report_period",
        "公布日": "ann_date",
        "会计准则": "accounting_standard",
        "销售商品、提供劳务收到的现金": "cash_received_from_sales",
        "收到的税费返还": "tax_refund_received",
        "收到的其他与经营活动有关的现金": "other_operating_cash_received",
        "经营活动现金流入小计": "operating_cash_inflow_subtotal",
        "购买商品、接受劳务支付的现金": "cash_paid_for_goods_services",
        "支付给职工以及为职工支付的现金": "cash_paid_to_employees",
        "支付的各项税费": "taxes_paid",
        "支付的其他与经营活动有关的现金": "other_operating_cash_paid",
        "经营活动现金流出小计": "operating_cash_outflow_subtotal",
        "经营活动产生的现金流量净额": "net_operating_cashflow",
        "收回投资所收到的现金": "cash_received_from_investment_recovery",
        "取得投资收益所收到的现金": "cash_received_from_invest_income",
        "处置固定资产、无形资产和其他长期资产而收回的现金净额": "cash_received_from_asset_disposal",
        "投资活动现金流入小计": "investing_cash_inflow_subtotal",
        "购建固定资产、无形资产和其他长期资产所支付的现金": "cash_paid_for_fixed_intangible_assets",
        "投资所支付的现金": "cash_paid_for_investments",
        "投资活动现金流出小计": "investing_cash_outflow_subtotal",
        "投资活动产生的现金流量净额": "net_investing_cashflow",
        "吸收权益性投资所收到的现金": "cash_received_from_equity_investment",
        "发行债券所收到的现金": "cash_received_from_bond_issue",
        "借款所收到的现金": "cash_received_from_borrowings",
        "筹资活动现金流入小计": "financing_cash_inflow_subtotal",
        "偿还债务所支付的现金": "cash_paid_for_debt_repayment",
        "分配股利或利润支付的现金": "cash_paid_for_dividend_profit",
        "偿付利息所支付的现金": "cash_paid_for_interest",
        "筹资活动现金流出小计": "financing_cash_outflow_subtotal",
        "筹资活动产生的现金流量净额": "net_financing_cashflow",
        "汇率变动对现金的影响": "fx_effect_on_cash",
        "现金及现金等价物净增加额": "net_increase_cash_equivalents",
        "期初现金及现金等价物余额": "cash_equivalents_begin",
        "期末现金及现金等价物余额": "cash_equivalents_end",
        "净利润": "net_profit",
        "固定资产折旧": "fixed_asset_depreciation",
        "无形资产摊销": "intangible_asset_amortization",
        "财务费用": "finance_expense",
        "投资损失(减：收益)": "investment_loss",
        "经营性应收项目的减少(减：增加)": "operating_receivables_decrease",
        "经营性应付项目的增加(减：减少)": "operating_payables_increase",
        "备注": "remark",
        "报告类型": "report_type",
    },
    date_field="公布日",
    code_batch_size=120,
    safe_query_required=True,
    date_columns=("report_date", "data_report_period", "ann_date"),
)

FINA_FORECAST = _stock_spec(
    "fina_forecast",
    40,
    "股票.业绩预测",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "截止日": "report_date",
        "公布日": "ann_date",
        "预警内容": "forecast_content",
        "预警类型": "forecast_type",
        "盈利金额下限": "profit_lower",
        "盈利金额上限": "profit_upper",
        "盈利金额单位": "profit_unit",
        "比上年同期增长下限(%)": "yoy_growth_lower_pct",
        "比上年同期增长上限(%)": "yoy_growth_upper_pct",
        "扣非后净利润预警类型": "excl_nr_profit_forecast_type",
        "扣非后净利润盈利金额下限": "excl_nr_profit_lower",
        "扣非后净利润盈利金额上限": "excl_nr_profit_upper",
        "营业收入预警类型": "revenue_forecast_type",
        "营业收入盈利金额下限": "revenue_lower",
        "营业收入盈利金额上限": "revenue_upper",
        "营业收入比上年同期增长下限(%)": "revenue_yoy_lower_pct",
        "营业收入比上年同期增长上限(%)": "revenue_yoy_upper_pct",
        "披露标识": "disclosure_flag",
        "预警详情": "forecast_detail",
        "备注": "remark",
    },
    date_field="公布日",
    code_batch_size=200,
    safe_query_required=True,
    date_columns=("report_date", "ann_date"),
    numeric_columns=(
        "profit_lower",
        "profit_upper",
        "yoy_growth_lower_pct",
        "yoy_growth_upper_pct",
        "excl_nr_profit_lower",
        "excl_nr_profit_upper",
        "revenue_lower",
        "revenue_upper",
        "revenue_yoy_lower_pct",
        "revenue_yoy_upper_pct",
    ),
)

FINA_EXPRESS = _stock_spec(
    "fina_express",
    41,
    "股票.业绩快报",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "截止日": "report_date",
        "公布日": "ann_date",
        "营业总收入": "total_revenue",
        "营业利润": "operate_profit",
        "利润总额": "total_profit",
        "归属于母公司所有者净利润": "parent_net_profit",
        "扣除非经常性损益后的净利润": "netprofit_excl_nr",
        "基本每股收益": "basic_eps",
        "净资产收益率(加权)(%)": "roe_weighted_pct",
        "资产总计": "total_assets",
        "归属母公司股东权益合计": "total_parent_equity",
        "股本": "share_capital",
        "每股净资产": "bps",
    },
    date_field="公布日",
    code_batch_size=200,
    safe_query_required=True,
    date_columns=("report_date", "ann_date"),
    numeric_columns=(
        "total_revenue",
        "operate_profit",
        "total_profit",
        "parent_net_profit",
        "netprofit_excl_nr",
        "basic_eps",
        "roe_weighted_pct",
        "total_assets",
        "total_parent_equity",
        "share_capital",
        "bps",
    ),
)

_FINA_MAINBZ_MAPPING = {
    "StockID": "tsl_code",
    "stockid": "tsl_code",
    "证券代码": "tsl_code",
    "截止日": "report_date",
    "数据报告期": "data_report_period",
    "产品名称": "segment_name",
    "主营业务收入": "main_business_revenue",
    "主营业务成本": "main_business_cost",
    "主营业务毛利": "main_business_gross_profit",
    "主营毛利率(%)": "main_business_gross_margin_pct",
    "主营业务收入所占比例(%)": "revenue_ratio_pct",
    "主营业务成本所占比例(%)": "cost_ratio_pct",
    "主营业务收入增长率(%)": "revenue_growth_pct",
    "主营业务成本增长率(%)": "cost_growth_pct",
    "主营毛利率增长率(%)": "gross_margin_growth_pct",
    "备注": "remark",
}

_FINA_MAINBZ_NUMERIC = (
    "main_business_revenue",
    "main_business_cost",
    "main_business_gross_profit",
    "main_business_gross_margin_pct",
    "revenue_ratio_pct",
    "cost_ratio_pct",
    "revenue_growth_pct",
    "cost_growth_pct",
    "gross_margin_growth_pct",
)

FINA_MAINBZ_INDUSTRY = _stock_spec(
    "fina_mainbz_industry",
    65,
    "股票.主营收入及成本分行业",
    dict(_FINA_MAINBZ_MAPPING),
    priority="P1",
    date_field="截止日",
    code_batch_size=160,
    safe_query_required=True,
    date_columns=("report_date", "data_report_period"),
    numeric_columns=_FINA_MAINBZ_NUMERIC,
    extra_columns=("segment_type",),
)

FINA_MAINBZ_PRODUCT = _stock_spec(
    "fina_mainbz_product",
    66,
    "股票.主营收入及成本分产品",
    dict(_FINA_MAINBZ_MAPPING),
    priority="P1",
    date_field="截止日",
    code_batch_size=160,
    safe_query_required=True,
    date_columns=("report_date", "data_report_period"),
    numeric_columns=_FINA_MAINBZ_NUMERIC,
    extra_columns=("segment_type",),
)

FINA_MAINBZ_AREA = _stock_spec(
    "fina_mainbz_area",
    67,
    "股票.主营收入及成本分地区",
    dict(_FINA_MAINBZ_MAPPING),
    priority="P1",
    date_field="截止日",
    code_batch_size=160,
    safe_query_required=True,
    date_columns=("report_date", "data_report_period"),
    numeric_columns=_FINA_MAINBZ_NUMERIC,
    extra_columns=("segment_type",),
)

STOCK_PUBLIC_TRADE_INFO = _stock_spec(
    "stock_public_trade_info",
    129,
    "股票.交易公开信息",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "截止日": "trade_date",
        "交易动作": "trade_action",
        "营业部全称": "broker_full_name",
        "买入金额": "buy_amount",
        "卖出金额": "sell_amount",
        "异动类型": "abnormal_type",
        "异动详情": "abnormal_detail",
        "机构简称": "institution_short_name",
        "营业部简称": "broker_short_name",
        "异动开始日": "abnormal_start_date",
        "异动截止日": "abnormal_end_date",
    },
    date_field="截止日",
    date_columns=("trade_date", "abnormal_start_date", "abnormal_end_date"),
    numeric_columns=("buy_amount", "sell_amount", "abnormal_type"),
    integer_columns=("abnormal_type",),
)

STOCK_UNLOCK_SCHEDULE = _stock_spec(
    "stock_unlock_schedule",
    154,
    "股票.限售解禁",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "解禁日": "unlock_date",
        "解禁数量": "unlock_volume",
        "实际可流通数量": "actual_float_volume",
        "限售类型": "lock_type",
    },
    date_field="解禁日",
    date_columns=("unlock_date",),
    numeric_columns=("unlock_volume", "actual_float_volume"),
)

STOCK_HOLDER_CHANGE_EXT = _stock_spec(
    "stock_holder_change_ext",
    157,
    "股票.股东增减持",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "变动开始日": "change_start_date",
        "变动截止日": "change_end_date",
        "公布日": "ann_date",
        "股东名称": "holder_name",
        "变动原因": "change_reason",
        "变动方向": "change_direction",
        "变动数量": "change_volume",
        "变动后持股数": "holding_after",
    },
    date_field="公布日",
    date_columns=("change_start_date", "change_end_date", "ann_date"),
    numeric_columns=("change_volume", "holding_after"),
)

STOCK_REPURCHASE_EXT = _stock_spec(
    "stock_repurchase_ext",
    160,
    "股票.股份回购",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "代码": "tsl_code",
        "首次信息发布日": "first_info_date",
        "截止日": "report_date",
        "公布日": "ann_date",
        "回购类型": "repurchase_type",
        "股票种类": "stock_type",
        "累计回购数量": "cum_repurchase_volume",
        "累计回购金额": "cum_repurchase_amount",
        "回购均价": "avg_price",
        "回购最高价": "high_price",
        "回购最低价": "low_price",
        "回购方案是否结束": "is_finished",
        "备注": "remark",
    },
    date_field="公布日",
    date_columns=("first_info_date", "report_date", "ann_date"),
    numeric_columns=("cum_repurchase_volume", "cum_repurchase_amount", "avg_price", "high_price", "low_price"),
)

STOCK_NAMECHANGE = _stock_spec(
    "stock_namechange",
    14,
    "股票.名称变更",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "变动日": "change_date",
        "变更前名称": "name_before",
        "变更后名称": "name_after",
        "备注": "remark",
    },
    priority="P1",
    date_field="变动日",
    code_batch_size=500,
    safe_query_required=True,
    date_columns=("change_date",),
)

STOCK_SHAREFLOAT = _stock_spec(
    "stock_sharefloat",
    16,
    "股票.股本结构",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "变动日": "change_date",
        "公布日": "ann_date",
        "总股本": "total_share",
        "A股": "a_share",
        "未流通股": "non_tradable_share",
        "无限售条件股份": "unrestricted_share",
        "流通 A 股": "float_a_share",
        "已上市流通 A 股": "listed_float_a_share",
        "B股": "b_share",
        "H股": "h_share",
        "变动原因": "change_reason",
        "有限售股份": "restricted_share",
        "其中：有限售国家股": "restricted_state_share",
        "其中：有限售国有法人股": "restricted_state_legal_person_share",
        "其中：有限售其他内资股": "restricted_other_domestic_share",
        "其中：有限售外资股": "restricted_foreign_share",
        "有限售 H 股": "restricted_h_share",
        "备注": "remark",
    },
    priority="P1",
    date_field="变动日",
    code_batch_size=500,
    safe_query_required=True,
    date_columns=("change_date", "ann_date"),
    numeric_columns=(
        "total_share",
        "a_share",
        "non_tradable_share",
        "unrestricted_share",
        "float_a_share",
        "listed_float_a_share",
        "b_share",
        "h_share",
        "restricted_share",
        "restricted_state_share",
        "restricted_state_legal_person_share",
        "restricted_other_domestic_share",
        "restricted_foreign_share",
        "restricted_h_share",
    ),
)

STOCK_DIVIDEND = _stock_spec(
    "stock_dividend",
    18,
    "股票.分红送股",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "截止日": "report_date",
        "实施公布日": "ann_date",
        "预案公布日": "proposal_ann_date",
        "股东大会日": "shareholder_meeting_date",
        "决案公布日": "resolution_ann_date",
        "股权登记日": "record_date",
        "除权除息日": "ex_date",
        "分红送股基数": "dividend_base",
        "红利比": "cash_dividend_ratio",
        "本币币种": "currency",
        "红利比(原币)": "cash_dividend_ratio_original",
        "原币币种": "original_currency",
        "汇率": "exchange_rate",
        "实得比": "actual_cash_ratio",
        "送股比": "bonus_share_ratio",
        "红股比": "bonus_stock_ratio",
        "转增比": "capitalization_ratio",
        "分红发放日": "pay_date",
        "送股上市日": "bonus_share_list_date",
        "预案预披露公布日": "pre_disclosure_ann_date",
        "备注": "remark",
    },
    priority="P1",
    date_field="实施公布日",
    code_batch_size=500,
    safe_query_required=True,
    date_columns=(
        "report_date",
        "ann_date",
        "proposal_ann_date",
        "shareholder_meeting_date",
        "resolution_ann_date",
        "record_date",
        "ex_date",
        "pay_date",
        "bonus_share_list_date",
        "pre_disclosure_ann_date",
    ),
    numeric_columns=(
        "dividend_base",
        "cash_dividend_ratio",
        "cash_dividend_ratio_original",
        "exchange_rate",
        "actual_cash_ratio",
        "bonus_share_ratio",
        "bonus_stock_ratio",
        "capitalization_ratio",
    ),
)

STOCK_HOLDERNUMBER = _stock_spec(
    "stock_holdernumber",
    28,
    "股票.股东户数",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "截止日": "report_date",
        "公布日": "ann_date",
        "股东人数": "holder_number",
        "备注": "remark",
    },
    priority="P1",
    date_field="公布日",
    code_batch_size=500,
    safe_query_required=True,
    date_columns=("report_date", "ann_date"),
    numeric_columns=("holder_number",),
)

_STOCK_HOLDER_COMMON_MAPPING = {
    "StockID": "tsl_code",
    "stockid": "tsl_code",
    "StockName": "stock_name",
    "证券代码": "tsl_code",
    "截止日": "report_date",
    "数据报告期": "data_report_period",
    "股东序号": "holder_rank",
    "名称": "holder_name",
    "股数": "holding_share",
    "占总股本比例(%)": "total_share_ratio_pct",
    "性质": "holder_nature",
    "所属券商": "broker",
    "所属基金代码": "fund_code_raw",
    "所属基金名称": "fund_name",
    "股东性质": "holder_type",
    "其中：有限售股数": "restricted_share",
    "其中：无限售股数": "unrestricted_share",
    "股权质押股数": "pledged_share",
    "股权冻结股数": "frozen_share",
    "备注": "remark",
}

STOCK_TOP10_HOLDER = _stock_spec(
    "stock_top10_holder",
    24,
    "股票.十大股东",
    dict(_STOCK_HOLDER_COMMON_MAPPING),
    priority="P1",
    date_field="截止日",
    code_batch_size=300,
    safe_query_required=True,
    date_columns=("report_date", "data_report_period"),
    numeric_columns=(
        "holder_rank",
        "holding_share",
        "total_share_ratio_pct",
        "restricted_share",
        "unrestricted_share",
        "pledged_share",
        "frozen_share",
    ),
    integer_columns=("holder_rank",),
)

STOCK_TOP10_FLOAT_HOLDER = _stock_spec(
    "stock_top10_float_holder",
    26,
    "股票.十大流通股东",
    dict(_STOCK_HOLDER_COMMON_MAPPING),
    priority="P1",
    date_field="截止日",
    code_batch_size=300,
    safe_query_required=True,
    date_columns=("report_date", "data_report_period"),
    numeric_columns=(
        "holder_rank",
        "holding_share",
        "total_share_ratio_pct",
        "restricted_share",
        "unrestricted_share",
        "pledged_share",
        "frozen_share",
    ),
    integer_columns=("holder_rank",),
)

STOCK_CONTROLLER = _stock_spec(
    "stock_controller",
    29,
    "股票.控股股东及实际控制人",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "stock_name",
        "证券代码": "tsl_code",
        "截止日": "report_date",
        "控制人名称": "controller_name",
        "控制人级别": "controller_level",
        "被控制人名称": "controlled_entity_name",
        "被控制人级别": "controlled_entity_level",
        "控制人持有被控制人比例(%)": "control_ratio_pct",
    },
    priority="P1",
    date_field="截止日",
    code_batch_size=500,
    safe_query_required=True,
    date_columns=("report_date",),
    numeric_columns=("control_ratio_pct",),
)

STOCK_OFFICER_HOLD_CHANGE = _stock_spec(
    "stock_officer_hold_change",
    30,
    "股票.董事、监事、高管持股变动",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "stock_name",
        "证券代码": "tsl_code",
        "变动开始日": "change_start_date",
        "变动截止日": "change_end_date",
        "公布日": "ann_date",
        "填报日期": "fill_date",
        "股东名称": "holder_name",
        "关联董监高姓名": "related_officer_name",
        "关联董监高职务": "related_officer_position",
        "与关联董监高关系": "related_officer_relation",
        "变动原因": "change_reason",
        "变动方向": "change_direction",
        "变动数量": "change_volume",
        "变动均价": "avg_change_price",
        "变动金额": "change_amount",
        "变动价格下限": "change_price_lower",
        "变动价格上限": "change_price_upper",
        "变动前持股数": "holding_before",
        "变动后持股数": "holding_after",
        "数据来源": "data_source",
        "股票种类": "stock_type",
    },
    priority="P1",
    date_field="公布日",
    code_batch_size=500,
    safe_query_required=True,
    date_columns=("change_start_date", "change_end_date", "ann_date", "fill_date"),
    numeric_columns=(
        "change_volume",
        "avg_change_price",
        "change_amount",
        "change_price_lower",
        "change_price_upper",
        "holding_before",
        "holding_after",
    ),
)

STOCK_FOREIGN_HOLDING = _stock_spec(
    "stock_foreign_holding",
    31,
    "股票.境外投资者持股信息",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "stock_name",
        "证券代码": "tsl_code",
        "截止日": "trade_date",
        "持有A股总数": "holding_a_share",
        "占总股本比例(%)": "total_share_ratio_pct",
    },
    priority="P1",
    date_field="截止日",
    code_batch_size=500,
    safe_query_required=True,
    date_columns=("trade_date",),
    numeric_columns=("holding_a_share", "total_share_ratio_pct"),
)

STOCK_NONRECURRING = _stock_spec(
    "stock_nonrecurring",
    150,
    "股票.非经常性损益",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "stock_name",
        "证券代码": "tsl_code",
        "截止日": "report_date",
        "公布日": "ann_date",
        "非流动性资产处置损益": "noncurrent_asset_disposal_profit_loss",
        "偶发性税收返还、减免": "occasional_tax_refund_reduction",
        "政府补助": "government_grant",
        "对非金融企业收取的资金占用费": "capital_occupation_fee_from_non_financial_enterprise",
        "投资成本小于被投资单位公允价值的收益": "bargain_purchase_investment_income",
        "非货币性资产交换损益": "non_monetary_asset_exchange_profit_loss",
        "委托他人投资或管理资产的损益": "entrusted_investment_profit_loss",
        "因不可抗力计提的资产减值准备": "force_majeure_asset_impairment_provision",
        "债务重组损益": "debt_restructuring_profit_loss",
        "企业重组费用": "enterprise_restructuring_expense",
        "显失公允交易超过公允价值的损益": "unfair_transaction_profit_loss",
        "合并子公司当期净损益": "subsidiary_combination_current_profit_loss",
        "或有事项产生的损益": "contingency_profit_loss",
        "公允价值变动损益、投资收益": "fair_value_change_and_investment_income",
        "应收款项减值准备转回": "receivable_impairment_reversal",
        "对外委托贷款取得的损益": "external_entrusted_loan_profit_loss",
        "投资性房地产公允价值变动损益": "investment_property_fair_value_change_profit_loss",
        "对当期损益一次性调整的影响": "one_time_current_profit_loss_adjustment",
        "受托经营取得的托管费收入": "entrusted_operation_fee_income",
        "其他营业外收入和支出": "other_non_operating_income_expense",
        "其他符合定义的损益项目": "other_nonrecurring_profit_loss",
        "所得税影响额": "income_tax_effect",
        "少数股东权益影响额": "minority_interest_effect",
        "合计": "total_nonrecurring_profit_loss",
        "备注": "remark",
    },
    priority="P1",
    date_field="公布日",
    code_batch_size=300,
    safe_query_required=True,
    date_columns=("report_date", "ann_date"),
    numeric_columns=(
        "noncurrent_asset_disposal_profit_loss",
        "occasional_tax_refund_reduction",
        "government_grant",
        "capital_occupation_fee_from_non_financial_enterprise",
        "bargain_purchase_investment_income",
        "non_monetary_asset_exchange_profit_loss",
        "entrusted_investment_profit_loss",
        "force_majeure_asset_impairment_provision",
        "debt_restructuring_profit_loss",
        "enterprise_restructuring_expense",
        "unfair_transaction_profit_loss",
        "subsidiary_combination_current_profit_loss",
        "contingency_profit_loss",
        "fair_value_change_and_investment_income",
        "receivable_impairment_reversal",
        "external_entrusted_loan_profit_loss",
        "investment_property_fair_value_change_profit_loss",
        "one_time_current_profit_loss_adjustment",
        "entrusted_operation_fee_income",
        "other_non_operating_income_expense",
        "other_nonrecurring_profit_loss",
        "income_tax_effect",
        "minority_interest_effect",
        "total_nonrecurring_profit_loss",
    ),
)

STOCK_TRADE_TIME = _stock_spec(
    "stock_trade_time",
    137,
    "股票.证券交易时间",
    {
        "StockID": "market_code",
        "stockid": "market_code",
        "StockName": "market_name_raw",
        "代码": "security_code_raw",
        "截止日": "effective_date",
        "竞价性质": "auction_type",
        "开始时间": "start_time",
        "截止时间": "end_time",
        "序号": "seq_no",
    },
    priority="P1",
    date_field="截止日",
    code_kind=None,
    code_batch_size=20,
    safe_query_required=True,
    date_columns=("effective_date",),
    numeric_columns=("seq_no",),
    integer_columns=("seq_no",),
)

FINA_DISCLOSURE = _stock_spec(
    "fina_disclosure",
    128,
    "股票.定期报告披露日期",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "截止日": "report_date",
        "首次预约日期": "first_scheduled_date",
        "第一次变更日期": "first_changed_date",
        "第二次变更日期": "second_changed_date",
        "第三次变更日期": "third_changed_date",
        "实际披露日期": "actual_disclosure_date",
        "首次预约公布日": "first_scheduled_ann_date",
        "第一次变更公布日": "first_changed_ann_date",
        "第二次变更公布日": "second_changed_ann_date",
        "第三次变更公布日": "third_changed_ann_date",
        "实际披露公布日": "actual_disclosure_ann_date",
    },
    priority="P0",
    date_field="截止日",
    code_batch_size=500,
    safe_query_required=True,
    date_columns=(
        "report_date",
        "first_scheduled_date",
        "first_changed_date",
        "second_changed_date",
        "third_changed_date",
        "actual_disclosure_date",
        "first_scheduled_ann_date",
        "first_changed_ann_date",
        "second_changed_ann_date",
        "third_changed_ann_date",
        "actual_disclosure_ann_date",
    ),
)

STOCK_BLOCKTRADE = _stock_spec(
    "stock_blocktrade",
    124,
    "股票.股票大宗交易",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "截止日": "trade_date",
        "成交价": "trade_price",
        "成交量": "trade_volume",
        "成交金额": "trade_amount",
        "买方营业部": "buyer_broker",
        "卖方营业部": "seller_broker",
        "是否为专场": "is_special_session",
        "买方机构名称": "buyer_institution",
        "卖方机构名称": "seller_institution",
    },
    priority="P1",
    date_field="截止日",
    code_batch_size=500,
    safe_query_required=True,
    date_columns=("trade_date",),
    numeric_columns=("trade_price", "trade_volume", "trade_amount"),
)

STOCK_MARGIN = _stock_spec(
    "stock_margin",
    165,
    "股票.融资融券汇总",
    {
        "StockID": "market_code",
        "stockid": "market_code",
        "证券代码": "market_code",
        "截止日": "trade_date",
        "融资买入额": "margin_buy_amount",
        "融资偿还额": "margin_repay_amount",
        "融资余额": "margin_balance",
        "融券卖出量": "short_sell_volume",
        "融券偿还量": "short_repay_volume",
        "融券余量": "short_balance_volume",
        "融券余额": "short_balance_amount",
        "融资融券余额": "margin_short_balance",
    },
    priority="P1",
    date_field="截止日",
    code_kind="margin_market",
    code_batch_size=3,
    safe_query_required=True,
    date_columns=("trade_date",),
    numeric_columns=(
        "margin_buy_amount",
        "margin_repay_amount",
        "margin_balance",
        "short_sell_volume",
        "short_repay_volume",
        "short_balance_volume",
        "short_balance_amount",
        "margin_short_balance",
    ),
)

STOCK_MARGINDETAIL = _stock_spec(
    "stock_margindetail",
    126,
    "股票.融资融券明细",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "截止日": "trade_date",
        "融资买入额": "margin_buy_amount",
        "融资偿还额": "margin_repay_amount",
        "融资余额": "margin_balance",
        "融券卖出量": "short_sell_volume",
        "融券偿还量": "short_repay_volume",
        "融券余量": "short_balance_volume",
        "融券余额": "short_balance_amount",
        "融资融券余额": "margin_short_balance",
    },
    priority="P1",
    date_field="截止日",
    code_batch_size=500,
    safe_query_required=True,
    date_columns=("trade_date",),
    numeric_columns=(
        "margin_buy_amount",
        "margin_repay_amount",
        "margin_balance",
        "short_sell_volume",
        "short_repay_volume",
        "short_balance_volume",
        "short_balance_amount",
        "margin_short_balance",
    ),
)

STOCK_MARGIN_COLLATERAL = _stock_spec(
    "stock_margin_collateral",
    164,
    "股票.融资融券担保券数据",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "截止日": "trade_date",
        "上一交易日担保证券数量": "prev_collateral_volume",
        "当日担保证券数量变动": "collateral_volume_change",
        "当日担保证券数量": "collateral_volume",
        "担保证券市值": "collateral_market_value",
        "证券总市值": "total_market_value",
        "担保证券市值占证券总市值比重(%)": "collateral_market_value_ratio_pct",
    },
    priority="P1",
    date_field="截止日",
    code_batch_size=500,
    safe_query_required=True,
    date_columns=("trade_date",),
    numeric_columns=(
        "prev_collateral_volume",
        "collateral_volume_change",
        "collateral_volume",
        "collateral_market_value",
        "total_market_value",
        "collateral_market_value_ratio_pct",
    ),
)

STOCK_HSGT_DAILY = _stock_spec(
    "stock_hsgt_daily",
    130,
    "股票.沪深港通每日成交汇总",
    {
        "截止日": "trade_date",
        "买入及卖出成交额(元)": "amount_total_rmb",
        "买入成交额(元)": "buy_amount_rmb",
        "卖出成交额(元)": "sell_amount_rmb",
        "买入及卖出成交额(港币)": "amount_total_hkd",
        "买入成交额(港币)": "buy_amount_hkd",
        "卖出成交额(港币)": "sell_amount_hkd",
        "买入及卖出成交数目": "trade_count_total",
        "买入成交数目": "buy_count",
        "卖出成交数目": "sell_count",
        "每日额度余额": "quota_balance",
        "股票买入及卖出成交额": "stock_etf_amount",
        "ETF 买入及卖出成交额": "etf_amount",
        "ETF买入及卖出成交额": "etf_amount",
    },
    date_field="截止日",
    code_kind="hsgt_channel",
    code_batch_size=4,
    date_columns=("trade_date",),
    postprocess="hsgt_channel",
    extra_columns=("channel_code", "channel_name"),
)

STOCK_HSGT_TOP10 = _stock_spec(
    "stock_hsgt_top10",
    131,
    "股票.沪深港通每日十大成交活跃股",
    {
        "截止日": "trade_date",
        "股票代码": "security_code_raw",
        "股票名称": "security_name",
        "买入金额": "buy_amount",
        "卖出金额": "sell_amount",
        "买入及卖出金额": "amount_total",
        "排名": "rank_no",
    },
    date_field="截止日",
    code_kind="hsgt_channel",
    code_batch_size=4,
    date_columns=("trade_date",),
    numeric_columns=("buy_amount", "sell_amount", "amount_total", "rank_no"),
    integer_columns=("rank_no",),
    postprocess="hsgt_channel",
    extra_columns=("channel_code", "channel_name"),
)

STOCK_HSGT_HOLD = _stock_spec(
    "stock_hsgt_hold",
    132,
    "股票.沪深港通持股明细",
    {
        "截止日": "trade_date",
        "股票代码": "security_code_raw",
        "证券代码": "security_code_raw",
        "代码": "security_code_raw",
        "StockName": "security_name",
        "股票名称": "security_name",
        "证券名称": "security_name",
        "名称": "security_name",
        "股数": "holding_volume",
        "持股数量": "holding_volume",
        "占总股本比例(%)": "total_share_ratio_pct",
    },
    date_field="截止日",
    code_kind="hsgt_stock",
    code_batch_size=500,
    date_columns=("trade_date",),
    numeric_columns=("holding_volume", "total_share_ratio_pct"),
    postprocess="hsgt_stock",
    extra_columns=("channel_code", "channel_name"),
)

STOCK_HSGT_SHORT_BALANCE = _stock_spec(
    "stock_hsgt_short_balance",
    161,
    "股票.沪深股通股票卖空数据",
    {
        "截止日": "trade_date",
        "股票代码": "security_code_raw",
        "证券代码": "security_code_raw",
        "代码": "security_code_raw",
        "StockName": "security_name",
        "股票名称": "security_name",
        "证券名称": "security_name",
        "名称": "security_name",
        "可供卖空股数余额": "short_balance_volume",
        "卖空股数余额": "short_balance_volume",
    },
    date_field="截止日",
    code_kind="hsgt_stock",
    code_batch_size=500,
    date_columns=("trade_date",),
    numeric_columns=("short_balance_volume",),
    postprocess="hsgt_stock",
    extra_columns=("channel_code", "channel_name"),
)

STOCK_LENDING_SUMMARY = _stock_spec(
    "stock_lending_summary",
    151,
    "股票.转融通证券出借交易",
    {"StockID": "tsl_code", "stockid": "tsl_code", "证券代码": "tsl_code", "截止日": "trade_date", "期限": "tenor_days", "费率(%)": "rate_pct", "费率": "rate_pct", "申报类型": "declare_type", "成交量": "deal_volume", "数据类型": "data_type"},
    priority="P1",
    date_field="截止日",
    date_columns=("trade_date",),
    numeric_columns=("tenor_days", "rate_pct", "deal_volume"),
    integer_columns=("tenor_days",),
)

STOCK_LENDING_TRADE = _stock_spec(
    "stock_lending_trade",
    152,
    "股票.转融券交易明细",
    {"StockID": "tsl_code", "stockid": "tsl_code", "证券代码": "tsl_code", "截止日": "trade_date", "期限": "tenor_days", "费率(%)": "rate_pct", "费率": "rate_pct", "融出数量": "lend_volume"},
    priority="P1",
    date_field="截止日",
    date_columns=("trade_date",),
    numeric_columns=("tenor_days", "rate_pct", "lend_volume"),
    integer_columns=("tenor_days",),
)

STOCK_LENDING_BALANCE = _stock_spec(
    "stock_lending_balance",
    153,
    "股票.转融券余量",
    {"StockID": "tsl_code", "stockid": "tsl_code", "证券代码": "tsl_code", "截止日": "trade_date", "余量": "balance_volume", "余额": "balance_amount"},
    date_field="截止日",
    date_columns=("trade_date",),
    numeric_columns=("balance_volume", "balance_amount"),
)

STOCK_PLEDGE_SUMMARY = _stock_spec(
    "stock_pledge_summary",
    144,
    "股票.股票质押回购交易汇总",
    {"代码": "market_code", "截止日": "trade_date", "初始交易金额": "initial_trade_amount", "购回交易金额": "repurchase_trade_amount"},
    priority="P1",
    date_field="截止日",
    code_kind="market",
    date_columns=("trade_date",),
    numeric_columns=("initial_trade_amount", "repurchase_trade_amount"),
)

STOCK_PLEDGE_DETAIL = _stock_spec(
    "stock_pledge_detail",
    145,
    "股票.股票质押回购交易明细",
    {"StockID": "tsl_code", "stockid": "tsl_code", "代码": "security_code_raw", "截止日": "trade_date", "初始交易数量": "initial_trade_volume", "购回交易数量": "repurchase_trade_volume"},
    priority="P1",
    date_field="截止日",
    date_columns=("trade_date",),
    numeric_columns=("initial_trade_volume", "repurchase_trade_volume"),
    extra_columns=("security_code_raw",),
)

STOCK_PLEDGE_BALANCE = _stock_spec(
    "stock_pledge_balance",
    146,
    "股票.股票质押回购余量",
    {"StockID": "tsl_code", "stockid": "tsl_code", "代码": "security_code_raw", "截止日": "trade_date", "余量": "balance_volume", "无限售股份余量": "unrestricted_balance_volume", "有限售股份余量": "restricted_balance_volume", "数据来源": "data_source"},
    priority="P1",
    date_field="截止日",
    date_columns=("trade_date",),
    numeric_columns=("balance_volume", "unrestricted_balance_volume", "restricted_balance_volume"),
)

STOCK_PLEDGE_RATE = _stock_spec(
    "stock_pledge_rate",
    147,
    "股票.股票质押回购平均质押率",
    {"代码": "market_code", "截止日": "trade_date", "无限售条件股份质押率(%)": "unrestricted_pledge_rate_pct", "有限售条件股份质押率(%)": "restricted_pledge_rate_pct"},
    priority="P1",
    date_field="截止日",
    code_kind="market",
    date_columns=("trade_date",),
    numeric_columns=("unrestricted_pledge_rate_pct", "restricted_pledge_rate_pct"),
)


stock_basic_ext = dataset_api(STOCK_BASIC_EXT)
stock_ipo = dataset_api(STOCK_IPO)
stock_delist_solution = dataset_api(STOCK_DELIST_SOLUTION)
stock_suspend = dataset_api(STOCK_SUSPEND)
stock_industry_versioned = dataset_api(STOCK_INDUSTRY_VERSIONED)
stock_classification_info = dataset_api(STOCK_CLASSIFICATION_INFO)
stock_fina_pit_ext = dataset_api(STOCK_FINA_PIT_EXT)
fina_indicator = dataset_api(FINA_INDICATOR)
fina_balancesheet = dataset_api(FINA_BALANCESHEET)
fina_income = dataset_api(FINA_INCOME)
fina_cashflow = dataset_api(FINA_CASHFLOW)
fina_forecast = dataset_api(FINA_FORECAST)
fina_express = dataset_api(FINA_EXPRESS)
fina_mainbz_industry = dataset_api(FINA_MAINBZ_INDUSTRY)
fina_mainbz_product = dataset_api(FINA_MAINBZ_PRODUCT)
fina_mainbz_area = dataset_api(FINA_MAINBZ_AREA)
stock_public_trade_info = dataset_api(STOCK_PUBLIC_TRADE_INFO)
stock_unlock_schedule = dataset_api(STOCK_UNLOCK_SCHEDULE)
stock_holder_change_ext = dataset_api(STOCK_HOLDER_CHANGE_EXT)
stock_repurchase_ext = dataset_api(STOCK_REPURCHASE_EXT)
stock_namechange = dataset_api(STOCK_NAMECHANGE)
stock_sharefloat = dataset_api(STOCK_SHAREFLOAT)
stock_dividend = dataset_api(STOCK_DIVIDEND)
stock_holdernumber = dataset_api(STOCK_HOLDERNUMBER)
stock_top10_holder = dataset_api(STOCK_TOP10_HOLDER)
stock_top10_float_holder = dataset_api(STOCK_TOP10_FLOAT_HOLDER)
stock_controller = dataset_api(STOCK_CONTROLLER)
stock_officer_hold_change = dataset_api(STOCK_OFFICER_HOLD_CHANGE)
stock_foreign_holding = dataset_api(STOCK_FOREIGN_HOLDING)
stock_nonrecurring = dataset_api(STOCK_NONRECURRING)
stock_trade_time = dataset_api(STOCK_TRADE_TIME)
fina_disclosure = dataset_api(FINA_DISCLOSURE)
stock_blocktrade = dataset_api(STOCK_BLOCKTRADE)
stock_margin = dataset_api(STOCK_MARGIN)
stock_margindetail = dataset_api(STOCK_MARGINDETAIL)
stock_margin_collateral = dataset_api(STOCK_MARGIN_COLLATERAL)
stock_hsgt_daily = dataset_api(STOCK_HSGT_DAILY)
stock_hsgt_top10 = dataset_api(STOCK_HSGT_TOP10)
stock_hsgt_hold = dataset_api(STOCK_HSGT_HOLD)
stock_hsgt_short_balance = dataset_api(STOCK_HSGT_SHORT_BALANCE)
stock_lending_summary = dataset_api(STOCK_LENDING_SUMMARY)
stock_lending_trade = dataset_api(STOCK_LENDING_TRADE)
stock_lending_balance = dataset_api(STOCK_LENDING_BALANCE)
stock_pledge_summary = dataset_api(STOCK_PLEDGE_SUMMARY)
stock_pledge_detail = dataset_api(STOCK_PLEDGE_DETAIL)
stock_pledge_balance = dataset_api(STOCK_PLEDGE_BALANCE)
stock_pledge_rate = dataset_api(STOCK_PLEDGE_RATE)


def fina_mainbz(
    codes=None,
    start_date=None,
    end_date=None,
    report_period=None,
    trade_date=None,
    refresh: bool = False,
    cache: bool = True,
    code_batch_size=None,
    max_codes=None,
    fields=None,
    all_history: bool = False,
    report_mode=None,
) -> pd.DataFrame:
    frames = []
    for segment_type, func in (
        ("industry", fina_mainbz_industry),
        ("product", fina_mainbz_product),
        ("area", fina_mainbz_area),
    ):
        frame = func(
            codes=codes,
            start_date=start_date,
            end_date=end_date,
            report_period=report_period,
            trade_date=trade_date,
            refresh=refresh,
            cache=cache,
            code_batch_size=code_batch_size,
            max_codes=max_codes,
            fields=fields,
            all_history=all_history,
            report_mode=report_mode,
        )
        if frame is not None and not frame.empty:
            frame = frame.copy()
            frame["segment_type"] = segment_type
            frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


__all__ = [
    "FINA_BALANCESHEET",
    "FINA_CASHFLOW",
    "FINA_DISCLOSURE",
    "FINA_EXPRESS",
    "FINA_FORECAST",
    "FINA_INCOME",
    "FINA_INDICATOR",
    "FINA_MAINBZ_AREA",
    "FINA_MAINBZ_INDUSTRY",
    "FINA_MAINBZ_PRODUCT",
    "STOCK_BLOCKTRADE",
    "STOCK_BASIC_EXT",
    "STOCK_CLASSIFICATION_INFO",
    "STOCK_CONTROLLER",
    "STOCK_DELIST_SOLUTION",
    "STOCK_DIVIDEND",
    "STOCK_FINA_PIT_EXT",
    "STOCK_FOREIGN_HOLDING",
    "STOCK_HOLDERNUMBER",
    "STOCK_HOLDER_CHANGE_EXT",
    "STOCK_HSGT_DAILY",
    "STOCK_HSGT_HOLD",
    "STOCK_HSGT_SHORT_BALANCE",
    "STOCK_HSGT_TOP10",
    "STOCK_INDUSTRY_VERSIONED",
    "STOCK_IPO",
    "STOCK_LENDING_BALANCE",
    "STOCK_LENDING_SUMMARY",
    "STOCK_LENDING_TRADE",
    "STOCK_MARGIN",
    "STOCK_MARGINDETAIL",
    "STOCK_MARGIN_COLLATERAL",
    "STOCK_NAMECHANGE",
    "STOCK_NONRECURRING",
    "STOCK_OFFICER_HOLD_CHANGE",
    "STOCK_PLEDGE_BALANCE",
    "STOCK_PLEDGE_DETAIL",
    "STOCK_PLEDGE_RATE",
    "STOCK_PLEDGE_SUMMARY",
    "STOCK_PUBLIC_TRADE_INFO",
    "STOCK_REPURCHASE_EXT",
    "STOCK_SHAREFLOAT",
    "STOCK_SUSPEND",
    "STOCK_TOP10_FLOAT_HOLDER",
    "STOCK_TOP10_HOLDER",
    "STOCK_TRADE_TIME",
    "STOCK_TTM_INDICATOR",
    "STOCK_UNLOCK_SCHEDULE",
    "STOCK_VALUATION_INDICATOR",
    "fina_balancesheet",
    "fina_cashflow",
    "fina_disclosure",
    "fina_express",
    "fina_forecast",
    "fina_income",
    "fina_indicator",
    "fina_mainbz",
    "fina_mainbz_area",
    "fina_mainbz_industry",
    "fina_mainbz_product",
    "stock_blocktrade",
    "stock_basic_ext",
    "stock_classification_info",
    "stock_controller",
    "stock_delist_solution",
    "stock_dividend",
    "stock_fina_pit_ext",
    "stock_foreign_holding",
    "stock_holdernumber",
    "stock_holder_change_ext",
    "stock_hsgt_daily",
    "stock_hsgt_hold",
    "stock_hsgt_short_balance",
    "stock_hsgt_top10",
    "stock_industry_versioned",
    "stock_ipo",
    "stock_lending_balance",
    "stock_lending_summary",
    "stock_lending_trade",
    "stock_margin",
    "stock_margindetail",
    "stock_margin_collateral",
    "stock_namechange",
    "stock_nonrecurring",
    "stock_officer_hold_change",
    "stock_pledge_balance",
    "stock_pledge_detail",
    "stock_pledge_rate",
    "stock_pledge_summary",
    "stock_public_trade_info",
    "stock_repurchase_ext",
    "stock_sharefloat",
    "stock_suspend",
    "stock_top10_float_holder",
    "stock_top10_holder",
    "stock_trade_time",
    "stock_ttm_indicator",
    "stock_unlock_schedule",
    "stock_valuation_indicator",
]

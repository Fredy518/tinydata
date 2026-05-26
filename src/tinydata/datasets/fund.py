"""Fund dataset APIs."""

from __future__ import annotations

import pandas as pd

from ..cache import CacheManager, make_cache_key
from ..client import TinyClient
from ..codes import normalize_codes
from ..errors import TinyDataParameterError
from ..infotable import format_tsl_datetime_literal, quote_tsl_string
from .specs import DatasetSpec, dataset_api, register_dataset
from .specs import process_dataset_frame


def _fund_spec(
    name: str,
    table_id: int,
    source_table_name: str,
    field_mapping: dict[str, str],
    *,
    priority: str = "P0",
    date_field: str | None = None,
    code_kind: str | None = "fund",
    code_batch_size: int = 500,
    safe_query_required: bool = False,
    date_columns: tuple[str, ...] = (),
    numeric_columns: tuple[str, ...] = (),
    integer_columns: tuple[str, ...] = (),
    allow_full_table: bool = False,
    code_transform: str | None = None,
) -> DatasetSpec:
    return register_dataset(
        DatasetSpec(
            name=name,
            domain="fund",
            priority=priority,
            table_id=table_id,
            source_table_name=source_table_name,
            field_mapping=field_mapping,
            date_field=date_field,
            allow_full_table=allow_full_table,
            code_kind=code_kind,
            code_pool=code_kind,
            code_batch_size=code_batch_size,
            date_columns=date_columns,
            numeric_columns=numeric_columns,
            integer_columns=integer_columns,
            safe_query_required=safe_query_required,
            code_transform=code_transform,
        )
    )


FUND_BASIC_EXT = _fund_spec(
    "fund_basic_ext",
    302,
    "基金.基金基本信息",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "基金名称": "fund_name",
        "基金简称": "fund_short_name",
        "基金类型": "fund_type",
        "交易方式": "trade_mode",
        "投资风格": "invest_style",
        "投资类型": "invest_type",
        "主动/被动": "active_passive",
        "投资区域": "invest_region",
        "份额类别": "share_class",
        "类别": "category",
        "净值增长率计算方法": "nav_return_method",
        "设立日": "found_date",
        "上市日": "list_date",
        "清算日": "liquidation_date",
        "基金管理人": "management",
        "基金管理人简称": "management_short_name",
        "基金托管人": "custodian",
        "业绩比较基准": "benchmark",
        "标的指数代码": "tracking_index_code_raw",
        "是否ETF联接": "is_etf_feeder",
        "ETF连接目标代码": "etf_target_code_raw",
        "ETF联接目标代码": "etf_target_code_raw",
        "上市地": "list_location",
        "交易代码": "trade_code",
        "不同收费模式基金主代码": "fee_mode_main_code_raw",
        "不同收费模式基金代码": "fee_mode_code_raw",
        "母基金代码": "parent_fund_code_raw",
        "分级A代码": "structured_a_code_raw",
        "分级B代码": "structured_b_code_raw",
        "分级基金类别": "structured_fund_type",
        "分级基金分拆比例": "structured_split_ratio",
        "封转开前基金代码": "pre_open_fund_code_raw",
        "封转开前基金名称": "pre_open_fund_name",
        "封转开后基金代码": "post_open_fund_code_raw",
        "封转开后基金名称": "post_open_fund_name",
        "投资目标": "investment_objective",
        "投资范围": "investment_scope",
        "投资策略": "investment_strategy",
        "风险收益特征": "risk_return_feature",
        "备注": "remark",
        "募集总金额": "raise_total_amount",
        "募集总份额": "raise_total_share",
    },
    code_batch_size=1000,
    date_columns=("found_date", "list_date", "liquidation_date"),
    numeric_columns=("structured_split_ratio", "raise_total_amount", "raise_total_share"),
)

FUND_MANAGER_EXT = _fund_spec(
    "fund_manager_ext",
    308,
    "基金.基金经理",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "fund_name",
        "证券代码": "tsl_code",
        "公布日": "ann_date",
        "信息来源": "info_source",
        "姓名": "manager_name",
        "性别": "gender",
        "国籍": "nationality",
        "出生年份": "birth_year",
        "年龄": "age",
        "职务": "position",
        "学历": "education",
        "证券从业经历": "securities_experience",
        "任职日": "begin_date",
        "离职日": "end_date",
        "在任与否": "is_current",
        "简历": "resume",
        "基金经理代码": "manager_code",
    },
    date_field="公布日",
    code_batch_size=1000,
    date_columns=("ann_date", "begin_date", "end_date"),
    numeric_columns=("age",),
    integer_columns=("age",),
)

FUND_BENCHMARK = _fund_spec(
    "fund_benchmark",
    303,
    "基金.业绩比较基准",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "fund_name",
        "证券代码": "tsl_code",
        "截止日": "report_date",
        "基准代码": "benchmark_code_raw",
        "基准名称": "benchmark_name",
        "比例(%)": "weight_pct",
        "浮动利率(%)": "floating_rate_pct",
        "年化收益率折算方法": "annual_return_method",
        "年化天数": "annual_days",
        "是否考虑非市场交易日基准收益率": "include_non_market_day_return",
        "浮动利率算法": "floating_rate_method",
        "复合收益率算法": "compound_return_method",
        "交易日类别": "trade_day_type",
    },
    priority="P1",
    date_field="截止日",
    code_batch_size=800,
    date_columns=("report_date",),
    numeric_columns=("weight_pct", "floating_rate_pct", "annual_days"),
    integer_columns=("annual_days",),
)

FUND_FEE = _fund_spec(
    "fund_fee",
    309,
    "基金.开放式基金费率",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "fund_name",
        "证券代码": "tsl_code",
        "公布日": "ann_date",
        "生效日": "effective_date",
        "费率类型": "fee_type",
        "前端后端": "front_back",
        "场内场外": "on_off_exchange",
        "金额下限": "amount_lower",
        "金额上限": "amount_upper",
        "持有年份下限": "holding_year_lower",
        "持有年份上限": "holding_year_upper",
        "费率(%)": "fee_rate_pct",
        "费率单位": "fee_unit",
    },
    priority="P1",
    code_batch_size=800,
    date_columns=("ann_date", "effective_date"),
    numeric_columns=("amount_lower", "amount_upper", "holding_year_lower", "holding_year_upper", "fee_rate_pct"),
)

_FUND_NAV_BENCHMARK_PERIODS = {
    "最近三个月": "last_3m",
    "最近六个月": "last_6m",
    "最近一年": "last_1y",
    "最近三年": "last_3y",
    "最近五年": "last_5y",
    "成立以来": "since_inception",
}

_FUND_NAV_BENCHMARK_MAPPING = {
    "StockID": "tsl_code",
    "stockid": "tsl_code",
    "StockName": "fund_name",
    "证券代码": "tsl_code",
    "截止日": "report_date",
}
for _source_prefix, _target_prefix in _FUND_NAV_BENCHMARK_PERIODS.items():
    _FUND_NAV_BENCHMARK_MAPPING.update(
        {
            f"{_source_prefix}净值增长率(%)": f"{_target_prefix}_nav_return_pct",
            f"{_source_prefix}净值增长率标准差(%)": f"{_target_prefix}_nav_return_std_pct",
            f"{_source_prefix}基准收益率(%)": f"{_target_prefix}_benchmark_return_pct",
            f"{_source_prefix}基准标准差(%)": f"{_target_prefix}_benchmark_std_pct",
            f"{_source_prefix}超额收益率(%)": f"{_target_prefix}_excess_return_pct",
            f"{_source_prefix}净值增长率标准差-基准标准差(%)": f"{_target_prefix}_nav_std_minus_benchmark_std_pct",
        }
    )

FUND_NAV_BENCHMARK_RETURN = _fund_spec(
    "fund_nav_benchmark_return",
    311,
    "基金.净值增长率与基准比较",
    dict(_FUND_NAV_BENCHMARK_MAPPING),
    priority="P1",
    date_field="截止日",
    code_batch_size=500,
    safe_query_required=True,
    date_columns=("report_date",),
    numeric_columns=tuple(
        value
        for value in _FUND_NAV_BENCHMARK_MAPPING.values()
        if value not in {"tsl_code", "fund_name", "report_date"}
    ),
    code_transform="fund_parent_if_present",
)

_FUND_BALANCE_SHEET_MAPPING = {
    "StockID": "tsl_code",
    "stockid": "tsl_code",
    "StockName": "fund_name",
    "证券代码": "tsl_code",
    "截止日": "report_date",
    "公布日": "ann_date",
    "现金": "cash",
    "银行存款": "bank_deposit",
    "清算备付金": "settlement_reserve",
    "交易保证金": "trading_deposit",
    "应收帐款": "accounts_receivable",
    "应收证券清算款": "securities_clearing_receivable",
    "应收股利": "dividend_receivable",
    "应收利息": "interest_receivable",
    "应收申购款": "subscription_receivable",
    "其他应收款": "other_receivables",
    "交易性金融资产": "trading_financial_assets",
    "股票投资市值": "stock_investment_market_value",
    "其中：股票投资成本": "stock_investment_cost",
    "股票投资估值增值": "stock_investment_valuation_gain",
    "债券投资市值": "bond_investment_market_value",
    "其中：债券投资成本": "bond_investment_cost",
    "债券投资估值增值": "bond_investment_valuation_gain",
    "其他投资市值": "other_investment_market_value",
    "其中：其他投资成本": "other_investment_cost",
    "其他投资估值增值": "other_investment_valuation_gain",
    "基金投资": "fund_investment",
    "资产支持证券投资": "abs_investment",
    "贵金属投资": "precious_metal_investment",
    "衍生金融资产": "derivative_financial_assets",
    "配股权证": "rights_warrants",
    "买入返售证券": "reverse_repo_securities",
    "债权投资": "debt_investment",
    "债权投资-其中：债券投资": "debt_investment_bond",
    "债权投资-其中：资产支持证券投资": "debt_investment_abs",
    "债权投资-其中：其他投资": "debt_investment_other",
    "其他债权投资": "other_debt_investment",
    "其他权益工具投资": "other_equity_instrument_investment",
    "待摊费用": "prepaid_expenses",
    "递延所得税资产": "deferred_tax_assets",
    "其他资产": "other_assets",
    "资产总计": "total_assets",
    "应付帐款": "accounts_payable",
    "应付证券清算款": "securities_clearing_payable",
    "应付赎回款": "redemption_payable",
    "应付赎回费": "redemption_fee_payable",
    "应付管理费": "management_fee_payable",
    "应付托管费": "custody_fee_payable",
    "业绩报酬": "performance_fee_payable",
    "应付佣金": "commission_payable",
    "应付配股款": "rights_issue_payable",
    "应付利息": "interest_payable",
    "未交税金": "taxes_payable",
    "应付收益": "income_payable",
    "应付债券分销款": "bond_distribution_payable",
    "其他应付款": "other_payables",
    "卖出回购证券款": "repo_sold_securities",
    "短期借款": "short_term_borrowing",
    "预提费用": "accrued_expenses",
    "其他负债": "other_liabilities",
    "交易性金融负债": "trading_financial_liabilities",
    "衍生金融负债": "derivative_financial_liabilities",
    "应付销售服务费": "sales_service_fee_payable",
    "递延所得税负债": "deferred_tax_liabilities",
    "负债合计": "total_liabilities",
    "实收基金": "paid_in_fund",
    "其他综合收益": "other_comprehensive_income",
    "未实现利得": "unrealized_gain",
    "其他权益": "other_equity",
    "未分配收益": "undistributed_income",
    "持有人权益合计": "total_holder_equity",
    "负债与持有人权益总计": "total_liabilities_and_holder_equity",
    "单位资产净值": "unit_net_asset",
    "基金份额总额": "total_fund_share",
    "备注": "remark",
    "应付投资顾问费": "investment_advisor_fee_payable",
    "应付运营服务费": "operation_service_fee_payable",
    "应付固定投资顾问费": "fixed_investment_advisor_fee_payable",
    "应付注册登记费": "registration_fee_payable",
    "期货暂收款": "futures_temporary_receipts",
    "个股期权": "stock_options",
    "理财投资": "wealth_management_investment",
    "信托投资": "trust_investment",
    "证券清算款": "securities_clearing_amount",
    "上海证券清算款": "sh_securities_clearing_amount",
    "深圳证券清算款": "sz_securities_clearing_amount",
    "场外证券清算款": "otc_securities_clearing_amount",
    "已实现利得": "realized_gain",
    "资产净值(费前)": "net_asset_before_fee",
    "资产净值(费后)": "net_asset_after_fee",
}

FUND_BALANCE_SHEET = _fund_spec(
    "fund_balance_sheet",
    312,
    "基金.资产负债表",
    dict(_FUND_BALANCE_SHEET_MAPPING),
    priority="P1",
    date_field="截止日",
    code_batch_size=300,
    safe_query_required=True,
    date_columns=("report_date", "ann_date"),
    numeric_columns=tuple(
        value
        for value in _FUND_BALANCE_SHEET_MAPPING.values()
        if value not in {"tsl_code", "fund_name", "report_date", "ann_date", "remark"}
    ),
    code_transform="fund_main_or_parent",
)

_FUND_INCOME_MAPPING = {
    "StockID": "tsl_code",
    "stockid": "tsl_code",
    "StockName": "fund_name",
    "证券代码": "tsl_code",
    "截止日": "report_date",
    "公布日": "ann_date",
    "证券买卖差价收入": "securities_trading_spread_income",
    "其中：股票买卖差价收入": "stock_trading_spread_income",
    "其中：债券买卖差价收入": "bond_trading_spread_income",
    "其中：基金投资收益": "fund_investment_income",
    "其中：资产支持证券投资收益": "abs_investment_income",
    "其中：贵金属投资收益": "precious_metal_investment_income",
    "其中：衍生工具收益": "derivative_income",
    "其中：以摊余成本计量的金融资产终止确认产生的收益": "amortized_cost_asset_derecognition_income",
    "其中：可转换债券买卖差价收入": "convertible_bond_trading_spread_income",
    "其中：配股权证收入": "rights_warrant_income",
    "其中：其他证券买卖差价收入": "other_securities_trading_spread_income",
    "投资收入合计": "total_investment_income",
    "其中：股票投资收益": "stock_investment_income",
    "其中：债券投资收益": "bond_investment_income",
    "其中：可转换债券投资收益": "convertible_bond_investment_income",
    "其中：其他投资收益": "other_investment_income",
    "存款利息收入": "deposit_interest_income",
    "其他收入": "other_income",
    "其中：回购利息收入": "repo_interest_income",
    "其中：其他利息收入": "other_interest_income",
    "发行费用结余收入": "issue_expense_surplus_income",
    "申购冻结利息收入": "subscription_freeze_interest_income",
    "买入返售证券收入": "reverse_repo_income",
    "其中：资产支持证券利息收入": "abs_interest_income",
    "其中：证券出借利息收入": "securities_lending_interest_income",
    "公允价值变动收益": "fair_value_change_income",
    "汇兑收益": "fx_income",
    "收入合计": "total_income",
    "管理费用": "management_fee",
    "业绩报酬": "performance_fee",
    "托管费用": "custody_fee",
    "销售服务费": "sales_service_fee",
    "交易费用": "trading_expense",
    "投资顾问费": "investment_advisor_fee",
    "回购交易费用": "repo_trading_expense",
    "回购利息支出": "repo_interest_expense",
    "卖出回购证券支出": "repo_sold_securities_expense",
    "利息支出": "interest_expense",
    "信用减值损失": "credit_impairment_loss",
    "税金及附加": "taxes_and_surcharges",
    "其他费用合计": "total_other_expenses",
    "其中：上市年费": "listing_annual_fee",
    "其中：会计师费": "accounting_fee",
    "其中：律师费": "legal_fee",
    "其中：持有人大会费": "holder_meeting_fee",
    "其中：信息披露费": "information_disclosure_fee",
    "其中：分红手续费": "dividend_handling_fee",
    "费用合计": "total_expenses",
    "利润总额": "total_profit",
    "所得税费用": "income_tax_expense",
    "以前年度损益调整(净收益)": "prior_year_profit_loss_adjustment_net_income",
    "净收益": "net_income",
    "未实现利得": "unrealized_gain",
    "基金经营业绩": "fund_operating_performance",
    "其他综合收益的税后净额": "other_comprehensive_income_after_tax",
    "综合收益总额": "total_comprehensive_income",
    "上期未分配净收益": "prior_period_undistributed_net_income",
    "移交基准日前未分配收益": "undistributed_income_before_transfer_base_date",
    "以前年度损益调整(未分配收益)": "prior_year_profit_loss_adjustment_undistributed_income",
    "本期损益平准金": "current_period_equalization",
    "本期申购基金单位的损益平准金": "subscription_equalization",
    "本期赎回基金单位的损益平准金": "redemption_equalization",
    "本期已分配收益": "distributed_income_current_period",
    "其他": "other",
    "期末可分配净收益": "ending_distributable_net_income",
    "期末未分配收益": "ending_undistributed_income",
    "备注": "remark",
}

FUND_INCOME_STATEMENT = _fund_spec(
    "fund_income_statement",
    314,
    "基金.收益及分配",
    dict(_FUND_INCOME_MAPPING),
    priority="P1",
    date_field="截止日",
    code_batch_size=300,
    safe_query_required=True,
    date_columns=("report_date", "ann_date"),
    numeric_columns=tuple(
        value
        for value in _FUND_INCOME_MAPPING.values()
        if value not in {"tsl_code", "fund_name", "report_date", "ann_date", "remark"}
    ),
    code_transform="fund_main_or_parent",
)

FUND_BUY_SELL = _fund_spec(
    "fund_buy_sell",
    319,
    "基金.累计买入和卖出",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "fund_name",
        "证券代码": "tsl_code",
        "截止日": "report_date",
        "序号": "rank_no",
        "股票代码": "stock_code_raw",
        "股票名称": "stock_name",
        "累计买入/卖出金额": "buy_sell_amount",
        "占期初净值比例(%)": "begin_nav_ratio_pct",
        "变动类型": "change_type",
        "备注": "remark",
    },
    priority="P1",
    date_field="截止日",
    code_batch_size=400,
    safe_query_required=True,
    date_columns=("report_date",),
    numeric_columns=("rank_no", "buy_sell_amount", "begin_nav_ratio_pct"),
    integer_columns=("rank_no",),
    code_transform="fund_main_or_parent",
)

FUND_DIVIDEND = _fund_spec(
    "fund_dividend",
    326,
    "基金.分红",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "fund_name",
        "证券代码": "tsl_code",
        "除权除息日": "ex_date",
        "场内除权除息日": "exchange_ex_date",
        "公布日": "ann_date",
        "股权登记日": "record_date",
        "分红年度": "dividend_year",
        "预案公布日": "proposal_ann_date",
        "股东大会日": "shareholder_meeting_date",
        "决案公布日": "resolution_ann_date",
        "红利比": "cash_dividend_ratio",
        "实得比": "actual_cash_ratio",
        "分红发放日": "pay_date",
        "分红金额": "dividend_amount",
        "备注": "remark",
        "更新时间": "update_time",
    },
    priority="P1",
    date_field="公布日",
    code_batch_size=500,
    safe_query_required=True,
    date_columns=(
        "ex_date",
        "exchange_ex_date",
        "ann_date",
        "record_date",
        "proposal_ann_date",
        "shareholder_meeting_date",
        "resolution_ann_date",
        "pay_date",
    ),
    numeric_columns=("dividend_year", "cash_dividend_ratio", "actual_cash_ratio", "dividend_amount"),
    integer_columns=("dividend_year",),
)

FUND_SPLIT = _fund_spec(
    "fund_split",
    327,
    "基金.份额拆分",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "fund_name",
        "证券代码": "tsl_code",
        "信息发布日期": "ann_date",
        "信息来源": "info_source",
        "信息类别": "info_type",
        "拆分折算日期": "split_date",
        "拆分折算比例": "split_ratio",
        "场内拆分折算日期": "exchange_split_date",
        "拆分折算后新增基金代码": "new_fund_code_raw",
        "分级基金折算类型": "structured_conversion_type",
        "更新时间": "update_time",
    },
    priority="P1",
    date_field="信息发布日期",
    code_batch_size=500,
    safe_query_required=True,
    date_columns=("ann_date", "split_date", "exchange_split_date"),
    numeric_columns=("split_ratio",),
)

FUND_NAMECHANGE = _fund_spec(
    "fund_namechange",
    359,
    "基金.基金信息变更",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "fund_name",
        "证券代码": "tsl_code",
        "属性代码": "attr_code",
        "属性名称": "attr_name",
        "数据类型": "data_type",
        "数值": "attr_value",
        "入选日期": "in_date",
        "剔除日期": "out_date",
        "最新标识": "is_latest",
        "备注": "remark",
        "更新时间": "update_time",
    },
    priority="P1",
    date_columns=("in_date", "out_date"),
    numeric_columns=("is_latest",),
    integer_columns=("is_latest",),
)

FUND_ETF_SUB_REDEMPTION = _fund_spec(
    "fund_etf_sub_redemption",
    346,
    "基金.ETF申购赎回-基本信息",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "fund_name",
        "证券代码": "tsl_code",
        "截止日": "trade_date",
        "最小申购、赎回单位的现金余额": "creation_redemption_cash_balance",
        "最小申购、赎回单位净值": "creation_redemption_unit_nav",
        "基金份额净值": "fund_unit_nav",
        "最小申购、赎回单位的预估现金部分": "estimated_cash_component",
        "现金替代比例上限(%)": "cash_substitution_limit_pct",
        "是否需要公布IOPV": "need_iopv",
        "最小申购、赎回单位": "creation_redemption_unit",
        "最小申购、赎回单位现金红利": "creation_redemption_cash_dividend",
        "申购赎回组合证券只数": "component_count",
        "是否开放申购": "is_subscription_open",
        "是否开放赎回": "is_redemption_open",
        "是否开放保证金申购": "is_margin_subscription_open",
        "保证金申购保证金率(%)": "margin_subscription_rate_pct",
        "保证金申购单一投资者当日申购总量限制": "margin_subscription_investor_daily_limit",
        "保证金申购单个代办证券公司当日申购总量限制": "margin_subscription_broker_daily_limit",
        "当日累计申购份额上限": "daily_subscription_share_limit",
        "当日累计赎回份额上限": "daily_redemption_share_limit",
        "单个账户当日累计申购份额上限": "account_daily_subscription_share_limit",
        "单个账户当日累计赎回份额上限": "account_daily_redemption_share_limit",
        "当日净申购份额上限": "daily_net_subscription_share_limit",
        "当日净赎回份额上限": "daily_net_redemption_share_limit",
        "单个账户当日净申购份额上限": "account_daily_net_subscription_share_limit",
        "单个账户当日净赎回份额上限": "account_daily_net_redemption_share_limit",
    },
    priority="P1",
    date_field="截止日",
    code_batch_size=200,
    safe_query_required=True,
    date_columns=("trade_date",),
    numeric_columns=(
        "creation_redemption_cash_balance",
        "creation_redemption_unit_nav",
        "fund_unit_nav",
        "estimated_cash_component",
        "cash_substitution_limit_pct",
        "creation_redemption_unit",
        "creation_redemption_cash_dividend",
        "component_count",
        "margin_subscription_rate_pct",
        "margin_subscription_investor_daily_limit",
        "margin_subscription_broker_daily_limit",
        "daily_subscription_share_limit",
        "daily_redemption_share_limit",
        "account_daily_subscription_share_limit",
        "account_daily_redemption_share_limit",
        "daily_net_subscription_share_limit",
        "daily_net_redemption_share_limit",
        "account_daily_net_subscription_share_limit",
        "account_daily_net_redemption_share_limit",
    ),
)

FUND_ETF_CONSTITUENT = register_dataset(
    DatasetSpec(
        name="fund_etf_constituent",
        domain="fund",
        priority="P1",
        table_id=0,
        source_table_name="GetFundETFConstituent",
        source_kind="tsl_function",
        field_mapping={
            "StockID": "tsl_code",
            "stockid": "tsl_code",
            "StockName": "fund_name",
            "证券代码": "tsl_code",
            "截止日": "trade_date",
            "代码": "component_code_raw",
            "名称": "component_name",
            "数量": "quantity",
            "现金替代标志": "cash_substitution_flag",
            "现金替代保证金率(%)": "cash_substitution_margin_rate_pct",
            "固定替代金额": "fixed_substitution_amount",
            "赎回现金替代保证金率(%)": "redemption_cash_substitution_margin_rate_pct",
            "赎回替代金额": "redemption_substitution_amount",
        },
        code_kind="fund",
        code_pool="fund",
        code_batch_size=1,
        date_columns=("trade_date",),
        numeric_columns=(
            "quantity",
            "cash_substitution_margin_rate_pct",
            "fixed_substitution_amount",
            "redemption_cash_substitution_margin_rate_pct",
            "redemption_substitution_amount",
        ),
        safe_query_required=True,
    )
)

FUND_NAV = _fund_spec(
    "fund_nav",
    328,
    "基金.净值",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "净值所在周": "nav_week",
        "截止日": "trade_date",
        "公布日": "ann_date",
        "单位净值": "unit_nav",
        "累计净值": "accum_nav",
        "每万份基金单位收益": "daily_profit_per_10k",
        "最近七日收益折算的年收益率(%)": "seven_day_annualized_return_pct",
        "备注": "remark",
        "更新时间": "update_time",
    },
    date_field="截止日",
    code_batch_size=800,
    safe_query_required=True,
    date_columns=("trade_date", "ann_date"),
    numeric_columns=("nav_week", "unit_nav", "accum_nav", "daily_profit_per_10k", "seven_day_annualized_return_pct"),
    integer_columns=("nav_week",),
)

FUND_SHARE = _fund_spec(
    "fund_share",
    324,
    "基金.份额变动",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "证券代码": "tsl_code",
        "变动日": "change_date",
        "信息来源": "info_source",
        "总份额": "total_share",
        "未流通份额": "non_tradable_share",
        "发起人持有份额": "sponsor_share",
        "流通份额": "tradable_share",
        "变动原因": "change_reason",
        "备注": "remark",
    },
    priority="P1",
    date_field="变动日",
    code_batch_size=800,
    safe_query_required=True,
    date_columns=("change_date",),
    numeric_columns=("total_share", "non_tradable_share", "sponsor_share", "tradable_share"),
)

FUND_FINANCIAL_QUARTERLY_EXT = _fund_spec(
    "fund_financial_quarterly_ext",
    310,
    "基金.基金财务指标(季度)",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "fund_name",
        "证券代码": "tsl_code",
        "截止日": "report_date",
        "公布日": "ann_date",
        "净收益": "net_income",
        "本期利润": "period_profit",
        "加权平均基金份额本期利润": "weighted_avg_share_profit",
        "单位净收益": "unit_net_income",
        "可分配净收益": "distributable_net_income",
        "单位可分配净收益": "unit_distributable_net_income",
        "资产总值": "total_asset",
        "资产净值": "net_asset",
        "单位资产净值": "unit_net_asset",
        "资产净值收益率(%)": "net_asset_return_pct",
        "资产净值增长率(%)": "net_asset_growth_pct",
        "累计净值增长率(%)": "cum_nav_growth_pct",
        "备注": "remark",
    },
    priority="P1",
    date_field="截止日",
    code_batch_size=500,
    safe_query_required=True,
    date_columns=("report_date", "ann_date"),
    numeric_columns=(
        "net_income",
        "period_profit",
        "weighted_avg_share_profit",
        "unit_net_income",
        "distributable_net_income",
        "unit_distributable_net_income",
        "total_asset",
        "net_asset",
        "unit_net_asset",
        "net_asset_return_pct",
        "net_asset_growth_pct",
        "cum_nav_growth_pct",
    ),
)

FUND_FOF_HOLDING_DETAIL = _fund_spec(
    "fund_fof_holding_detail",
    349,
    "基金.基金明细",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "fund_name",
        "截止日": "report_date",
        "名称": "holding_name",
        "代码": "holding_code_raw",
        "数量": "quantity",
        "市值": "market_value",
        "占净值比例(%)": "nav_ratio_pct",
        "市值排名": "rank_no",
        "是否属于关联基金": "is_related_fund",
    },
    priority="P2",
    date_field="截止日",
    code_kind="fof_fund",
    code_batch_size=500,
    safe_query_required=True,
    date_columns=("report_date",),
    numeric_columns=("quantity", "market_value", "nav_ratio_pct", "rank_no"),
    integer_columns=("rank_no",),
)

FUND_STOCK_HOLDING_DETAIL = _fund_spec(
    "fund_stock_holding_detail",
    318,
    "基金.持股明细",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "fund_name",
        "截止日": "report_date",
        "公布日": "ann_date",
        "代码": "security_code_raw",
        "名称": "security_name",
        "数量": "quantity",
        "市值": "market_value",
        "占净值比例(%)": "nav_ratio_pct",
        "市值排名": "rank_no",
        "其中:指数投资部分数量": "index_invest_quantity",
        "其中：指数投资部分数量": "index_invest_quantity",
        "其中:指数投资部分市值": "index_invest_market_value",
        "其中：指数投资部分市值": "index_invest_market_value",
        "其中:指数投资部分占净值比例(%)": "index_invest_nav_ratio_pct",
        "其中：指数投资部分占净值比例(%)": "index_invest_nav_ratio_pct",
        "其中:积极投资部分数量": "active_invest_quantity",
        "其中：积极投资部分数量": "active_invest_quantity",
        "其中:积极投资部分市值": "active_invest_market_value",
        "其中：积极投资部分市值": "active_invest_market_value",
        "其中:积极投资部分占净值比例(%)": "active_invest_nav_ratio_pct",
        "其中：积极投资部分占净值比例(%)": "active_invest_nav_ratio_pct",
        "板块名称": "board_name",
        "备注": "remark",
    },
    date_field="截止日",
    code_batch_size=500,
    safe_query_required=True,
    date_columns=("report_date", "ann_date"),
    numeric_columns=(
        "quantity",
        "market_value",
        "nav_ratio_pct",
        "rank_no",
        "index_invest_quantity",
        "index_invest_market_value",
        "index_invest_nav_ratio_pct",
        "active_invest_quantity",
        "active_invest_market_value",
        "active_invest_nav_ratio_pct",
    ),
    integer_columns=("rank_no",),
    code_transform="fund_main_or_parent",
)

FUND_INDUSTRY_ALLOC = _fund_spec(
    "fund_industry_alloc",
    320,
    "基金.行业配置",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "fund_name",
        "截止日": "report_date",
        "公布日": "ann_date",
        "行业名称": "industry_name",
        "市值": "market_value",
        "占净值比例(%)": "nav_ratio_pct",
        "备注": "remark",
    },
    date_field="截止日",
    safe_query_required=True,
    date_columns=("report_date", "ann_date"),
    numeric_columns=("market_value", "nav_ratio_pct"),
    code_transform="fund_main_or_parent",
)

FUND_ASSET_ALLOC = _fund_spec(
    "fund_asset_alloc",
    322,
    "基金.资产配置",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "fund_name",
        "截止日": "report_date",
        "公布日": "ann_date",
        "权益投资": "equity_investment",
        "权益投资占净值比例(%)": "equity_nav_ratio_pct",
        "股票市值": "stock_market_value",
        "股票占净值比例(%)": "stock_nav_ratio_pct",
        "基金市值": "fund_market_value",
        "基金市值占净值比例(%)": "fund_nav_ratio_pct",
        "固定收益投资": "fixed_income_investment",
        "固定收益投资占净值比例(%)": "fixed_income_nav_ratio_pct",
        "债券市值": "bond_market_value",
        "债券占净值比例(%)": "bond_nav_ratio_pct",
        "资产支持证券市值": "abs_market_value",
        "资产支持证券市值占净值比例(%)": "abs_nav_ratio_pct",
        "银行存款和清算备付金市值": "bank_deposit_settlement_value",
        "银行存款和清算备付金占净值比例(%)": "bank_deposit_settlement_nav_ratio_pct",
        "买入返售证券市值": "reverse_repo_value",
        "买入返售证券占净值比例(%)": "reverse_repo_nav_ratio_pct",
        "卖出回购证券市值": "repo_sold_value",
        "卖出回购证券占净值比例(%)": "repo_sold_nav_ratio_pct",
        "其他资产市值": "other_asset_value",
        "其他资产占净值比例(%)": "other_asset_nav_ratio_pct",
        "金融衍生品市值": "derivative_value",
        "金融衍生品市值占净值比例(%)": "derivative_nav_ratio_pct",
        "资产净值": "net_asset_value",
        "资产总值": "total_asset_value",
        "备注": "remark",
    },
    date_field="截止日",
    safe_query_required=True,
    date_columns=("report_date", "ann_date"),
    code_transform="fund_main_or_parent",
)

FUND_BOND_ALLOC = _fund_spec(
    "fund_bond_alloc",
    340,
    "基金.债券配置",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "fund_name",
        "截止日": "report_date",
        "公布日": "ann_date",
        "行业名称": "bond_category",
        "市值": "market_value",
        "占净值比例(%)": "nav_ratio_pct",
        "占债券市值比例(%)": "bond_market_ratio_pct",
        "备注": "remark",
    },
    priority="P1",
    date_field="截止日",
    safe_query_required=True,
    date_columns=("report_date", "ann_date"),
    numeric_columns=("market_value", "nav_ratio_pct", "bond_market_ratio_pct"),
    code_transform="fund_main_or_parent",
)

FUND_BOND_HOLDING_DETAIL = _fund_spec(
    "fund_bond_holding_detail",
    342,
    "基金.持债明细",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "fund_name",
        "截止日": "report_date",
        "公布日": "ann_date",
        "名称": "bond_name",
        "代码": "bond_code_raw",
        "数量": "quantity",
        "市值": "market_value",
        "占净值比例(%)": "nav_ratio_pct",
        "市值排名": "rank_no",
        "债券类型": "bond_type",
        "是否处于转股期": "is_convertible_period",
        "备注": "remark",
    },
    date_field="截止日",
    safe_query_required=True,
    date_columns=("report_date", "ann_date"),
    numeric_columns=("quantity", "market_value", "nav_ratio_pct", "rank_no"),
    integer_columns=("rank_no",),
    code_transform="fund_main_or_parent",
)

FUND_ABS_HOLDING_DETAIL = _fund_spec(
    "fund_abs_holding_detail",
    350,
    "基金.资产支持证券明细",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "fund_name",
        "截止日": "report_date",
        "名称": "asset_name",
        "代码": "asset_code_raw",
        "数量": "quantity",
        "市值": "market_value",
        "占净值比例(%)": "nav_ratio_pct",
        "市值排名": "rank_no",
    },
    priority="P2",
    date_field="截止日",
    safe_query_required=True,
    date_columns=("report_date",),
    numeric_columns=("quantity", "market_value", "nav_ratio_pct", "rank_no"),
    integer_columns=("rank_no",),
)

FUND_CBOND_HOLDING_DETAIL = _fund_spec(
    "fund_cbond_holding_detail",
    354,
    "基金.可转债明细",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "fund_name",
        "截止日": "report_date",
        "名称": "cbond_name",
        "代码": "cbond_code_raw",
        "数量": "quantity",
        "市值": "market_value",
        "占净值比例(%)": "nav_ratio_pct",
        "市值排名": "rank_no",
    },
    priority="P2",
    date_field="截止日",
    safe_query_required=True,
    date_columns=("report_date",),
    numeric_columns=("quantity", "market_value", "nav_ratio_pct", "rank_no"),
    integer_columns=("rank_no",),
)

FUND_TOP_HOLDER = _fund_spec(
    "fund_top_holder",
    330,
    "基金.主要持有人",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "fund_name",
        "截止日": "report_date",
        "公布日": "ann_date",
        "名称": "holder_name",
        "份额": "holding_share",
        "占总份额比例(%)": "total_share_ratio_pct",
        "性质": "holder_type",
        "备注": "remark",
    },
    priority="P1",
    date_field="截止日",
    code_batch_size=500,
    safe_query_required=True,
    date_columns=("report_date", "ann_date"),
    numeric_columns=("holding_share", "total_share_ratio_pct"),
)

FUND_HOLDER_STRUCTURE = _fund_spec(
    "fund_holder_structure",
    331,
    "基金.持有人结构",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "fund_name",
        "截止日": "report_date",
        "持有人户数": "holder_count",
        "户均持有份额": "avg_share_per_holder",
        "机构持有份额": "institution_share",
        "机构持有比例(%)": "institution_ratio_pct",
        "个人持有份额": "individual_share",
        "个人持有比例(%)": "individual_ratio_pct",
        "其他持有份额": "other_share",
        "其他持有比例(%)": "other_ratio_pct",
        "备注": "remark",
        "基金管理人从业人员持有份额": "staff_share",
        "基金管理人从业人员持有比例(%)": "staff_ratio_pct",
    },
    date_field="截止日",
    code_batch_size=800,
    safe_query_required=True,
    date_columns=("report_date",),
)

FUND_BROKER_SEAT = _fund_spec(
    "fund_broker_seat",
    332,
    "基金.交易席位情况",
    {
        "StockID": "tsl_code",
        "stockid": "tsl_code",
        "StockName": "fund_name",
        "截止日": "report_date",
        "公布日": "ann_date",
        "券商名称": "broker_name",
        "交易单元数量": "trading_unit_count",
        "股票成交量": "stock_trade_amount",
        "占股票成交总量比例(%)": "stock_trade_ratio_pct",
        "佣金": "commission",
        "占佣金总量比例(%)": "commission_ratio_pct",
        "债券成交量": "bond_trade_amount",
        "占债券成交总量比例(%)": "bond_trade_ratio_pct",
        "回购成交量": "repo_trade_amount",
        "占回购成交总量比例(%)": "repo_trade_ratio_pct",
        "银行间债券成交量": "interbank_bond_trade_amount",
        "占银行间债券成交总量比例(%)": "interbank_bond_trade_ratio_pct",
        "权证成交金额": "warrant_trade_amount",
        "占权证成交总额比例(%)": "warrant_trade_ratio_pct",
        "基金成交金额": "fund_trade_amount",
        "占基金成交总额比例(%)": "fund_trade_ratio_pct",
        "备注": "remark",
    },
    priority="P1",
    date_field="截止日",
    code_batch_size=400,
    safe_query_required=True,
    date_columns=("report_date", "ann_date"),
    code_transform="fund_main_or_parent",
)

FUND_CLASSIFICATION_INFO = _fund_spec(
    "fund_classification_info",
    355,
    "基金.基金分类信息",
    {
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
    code_kind=None,
    allow_full_table=True,
    date_columns=("in_date", "out_date"),
    numeric_columns=("level_no", "is_latest"),
    integer_columns=("level_no", "is_latest"),
)

FUND_CLASSIFICATION_MEMBER = _fund_spec(
    "fund_classification_member",
    356,
    "基金.基金分类",
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
    code_batch_size=1000,
    date_columns=("in_date", "out_date"),
    numeric_columns=("level_no", "is_latest"),
    integer_columns=("level_no", "is_latest"),
)


def fund_etf_constituent(
    codes=None,
    trade_date=None,
    refresh: bool = False,
    cache: bool = True,
    max_codes=None,
) -> pd.DataFrame:
    """Fetch ETF PCF constituents through Tinysoft GetFundETFConstituent."""

    if trade_date in (None, ""):
        raise TinyDataParameterError("fund_etf_constituent requires trade_date.")
    normalized = normalize_codes(codes, kind="fund")
    if not normalized:
        raise TinyDataParameterError("fund_etf_constituent requires one or more ETF fund codes.")
    if max_codes is not None:
        normalized = normalized[: max(1, int(max_codes))]

    manager = CacheManager()
    key = make_cache_key(
        FUND_ETF_CONSTITUENT.name,
        {"codes": normalized, "trade_date": trade_date, "field_version": FUND_ETF_CONSTITUENT.field_version},
    )
    if cache and not refresh:
        cached = manager.read(FUND_ETF_CONSTITUENT.name, key)
        if cached is not None:
            return cached

    date_literal = format_tsl_datetime_literal(trade_date)
    client = TinyClient()
    frames = []
    for code in normalized:
        tsl = (
            f'Ret:=GetFundETFConstituent("{code}",{date_literal},t);'
            'If Ret then Return t; Else Return array();'
        )
        raw = client.exec(tsl, as_dataframe=True)
        if raw is not None and not raw.empty:
            frames.append(process_dataset_frame(raw, FUND_ETF_CONSTITUENT))

    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if cache:
        manager.write(FUND_ETF_CONSTITUENT.name, key, out)
    return out


FUND_ADJUSTED_NAV = register_dataset(
    DatasetSpec(
        name="fund_adjusted_nav",
        domain="fund",
        priority="P1",
        table_id=0,
        source_table_name="FundNAWByRateBegtEndt",
        source_kind="tsl_function",
        field_mapping={
            "StockID": "tsl_code",
            "stockid": "tsl_code",
            "证券代码": "tsl_code",
            "截止日": "trade_date",
            "日期": "trade_date",
            "单位净值": "unit_nav",
            "累计净值": "accum_nav",
            "复权净值": "adjusted_nav",
            "复权因子": "adjust_factor",
            "复权净值增长率(%)": "adjusted_return_pct",
            "份额拆分比": "split_ratio",
            "红利比": "dividend_ratio",
        },
        code_kind="fund",
        code_pool="fund",
        code_batch_size=1,
        safe_query_required=True,
        date_columns=("trade_date",),
        numeric_columns=(
            "unit_nav",
            "accum_nav",
            "adjusted_nav",
            "adjust_factor",
            "adjusted_return_pct",
            "split_ratio",
            "dividend_ratio",
        ),
        extra_columns=("adjust", "adjust_date", "begin_date", "end_date"),
    )
)


def fund_adjusted_nav(
    codes=None,
    start_date=None,
    end_date=None,
    *,
    adjust: int = 1,
    adjust_date=-1,
    refresh: bool = False,
    cache: bool = True,
    max_codes=None,
) -> pd.DataFrame:
    """Fetch fund adjusted NAV through Tinysoft ``FundNAWByRateBegtEndt``.

    Parameters mirror Tinysoft system parameters: ``adjust`` -> ``pn_rate()``
    (1 = ratio adjust, 2 = complex adjust), ``adjust_date`` -> ``PN_RateDay()``
    where ``-1`` uses fund inception (back-adjusted) and ``0`` uses the last
    quoted NAV date (forward-adjusted). Non-zero adjust modes are required —
    use ``fund_nav`` for unadjusted NAVs.
    """

    if adjust in (None, 0):
        raise TinyDataParameterError(
            "fund_adjusted_nav requires adjust in {1, 2}; use fund_nav for unadjusted NAV."
        )
    if start_date in (None, "") or end_date in (None, ""):
        raise TinyDataParameterError("fund_adjusted_nav requires both start_date and end_date.")
    normalized = normalize_codes(codes, kind="fund")
    if not normalized:
        raise TinyDataParameterError("fund_adjusted_nav requires one or more fund codes.")
    if max_codes is not None:
        normalized = normalized[: max(1, int(max_codes))]

    manager = CacheManager()
    cache_payload = {
        "codes": normalized,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "adjust": int(adjust),
        "adjust_date": str(adjust_date),
        "field_version": FUND_ADJUSTED_NAV.field_version,
    }
    key = make_cache_key(FUND_ADJUSTED_NAV.name, cache_payload)
    if cache and not refresh:
        cached = manager.read(FUND_ADJUSTED_NAV.name, key)
        if cached is not None:
            return cached

    begin_literal = format_tsl_datetime_literal(start_date)
    end_literal = format_tsl_datetime_literal(end_date)

    if adjust_date in (-1, 0):
        rateday_literal = str(int(adjust_date))
    else:
        rateday_literal = format_tsl_datetime_literal(adjust_date)

    client = TinyClient()
    frames: list[pd.DataFrame] = []
    for code in normalized:
        tsl = (
            f"setsysparam(pn_stock(),{quote_tsl_string(code)});"
            f"setsysparam(pn_rate(),{int(adjust)});"
            f"setsysparam(PN_RateDay(),{rateday_literal});"
            f"Ret:=FundNAWByRateBegtEndt({begin_literal},{end_literal});"
            "If istable(Ret) then Return Ret; Else Return array();"
        )
        raw = client.exec(tsl, as_dataframe=True)
        if raw is None or raw.empty:
            continue
        raw = raw.copy()
        raw["StockID"] = code
        processed = process_dataset_frame(raw, FUND_ADJUSTED_NAV)
        processed["adjust"] = int(adjust)
        processed["adjust_date"] = str(adjust_date)
        processed["begin_date"] = pd.to_datetime(start_date, errors="coerce")
        processed["end_date"] = pd.to_datetime(end_date, errors="coerce")
        frames.append(processed)

    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if cache:
        manager.write(FUND_ADJUSTED_NAV.name, key, out)
    return out


fund_basic_ext = dataset_api(FUND_BASIC_EXT)
fund_basic = fund_basic_ext
fund_manager_ext = dataset_api(FUND_MANAGER_EXT)
fund_manager = fund_manager_ext
fund_benchmark = dataset_api(FUND_BENCHMARK)
fund_fee = dataset_api(FUND_FEE)
fund_nav_benchmark_return = dataset_api(FUND_NAV_BENCHMARK_RETURN)
fund_balance_sheet = dataset_api(FUND_BALANCE_SHEET)
fund_income_statement = dataset_api(FUND_INCOME_STATEMENT)
fund_buy_sell = dataset_api(FUND_BUY_SELL)
fund_dividend = dataset_api(FUND_DIVIDEND)
fund_split = dataset_api(FUND_SPLIT)
fund_namechange = dataset_api(FUND_NAMECHANGE)
fund_etf_sub_redemption = dataset_api(FUND_ETF_SUB_REDEMPTION)
fund_nav = dataset_api(FUND_NAV)
fund_share = dataset_api(FUND_SHARE)
fund_financial_quarterly_ext = dataset_api(FUND_FINANCIAL_QUARTERLY_EXT)
fund_fof_holding_detail = dataset_api(FUND_FOF_HOLDING_DETAIL)
fund_stock_holding_detail = dataset_api(FUND_STOCK_HOLDING_DETAIL)
fund_stock_holding = fund_stock_holding_detail
fund_industry_alloc = dataset_api(FUND_INDUSTRY_ALLOC)
fund_asset_alloc = dataset_api(FUND_ASSET_ALLOC)
fund_bond_alloc = dataset_api(FUND_BOND_ALLOC)
fund_bond_holding_detail = dataset_api(FUND_BOND_HOLDING_DETAIL)
fund_bond_holding = fund_bond_holding_detail
fund_abs_holding_detail = dataset_api(FUND_ABS_HOLDING_DETAIL)
fund_cbond_holding_detail = dataset_api(FUND_CBOND_HOLDING_DETAIL)
fund_top_holder = dataset_api(FUND_TOP_HOLDER)
fund_holder_structure = dataset_api(FUND_HOLDER_STRUCTURE)
fund_broker_seat = dataset_api(FUND_BROKER_SEAT)
fund_classification_info = dataset_api(FUND_CLASSIFICATION_INFO)
fund_classification_member = dataset_api(FUND_CLASSIFICATION_MEMBER)


__all__ = [
    "FUND_ABS_HOLDING_DETAIL",
    "FUND_ADJUSTED_NAV",
    "FUND_ASSET_ALLOC",
    "FUND_BALANCE_SHEET",
    "FUND_BENCHMARK",
    "FUND_BASIC_EXT",
    "FUND_BOND_ALLOC",
    "FUND_BOND_HOLDING_DETAIL",
    "FUND_BROKER_SEAT",
    "FUND_BUY_SELL",
    "FUND_CBOND_HOLDING_DETAIL",
    "FUND_CLASSIFICATION_INFO",
    "FUND_CLASSIFICATION_MEMBER",
    "FUND_DIVIDEND",
    "FUND_ETF_CONSTITUENT",
    "FUND_ETF_SUB_REDEMPTION",
    "FUND_FEE",
    "FUND_FINANCIAL_QUARTERLY_EXT",
    "FUND_FOF_HOLDING_DETAIL",
    "FUND_HOLDER_STRUCTURE",
    "FUND_INCOME_STATEMENT",
    "FUND_INDUSTRY_ALLOC",
    "FUND_MANAGER_EXT",
    "FUND_NAMECHANGE",
    "FUND_NAV",
    "FUND_NAV_BENCHMARK_RETURN",
    "FUND_SHARE",
    "FUND_SPLIT",
    "FUND_STOCK_HOLDING_DETAIL",
    "FUND_TOP_HOLDER",
    "fund_abs_holding_detail",
    "fund_asset_alloc",
    "fund_adjusted_nav",
    "fund_balance_sheet",
    "fund_benchmark",
    "fund_basic",
    "fund_basic_ext",
    "fund_bond_alloc",
    "fund_bond_holding",
    "fund_bond_holding_detail",
    "fund_broker_seat",
    "fund_buy_sell",
    "fund_cbond_holding_detail",
    "fund_classification_info",
    "fund_classification_member",
    "fund_dividend",
    "fund_etf_constituent",
    "fund_etf_sub_redemption",
    "fund_fee",
    "fund_financial_quarterly_ext",
    "fund_fof_holding_detail",
    "fund_holder_structure",
    "fund_income_statement",
    "fund_industry_alloc",
    "fund_manager",
    "fund_manager_ext",
    "fund_namechange",
    "fund_nav",
    "fund_nav_benchmark_return",
    "fund_share",
    "fund_split",
    "fund_stock_holding",
    "fund_stock_holding_detail",
    "fund_top_holder",
]

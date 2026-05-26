# tinydata

`tinydata` 是一个基于天软 TS-OPI 的轻量级直连数据接口包。它是独立 Python library，运行时不依赖 AlphaHome、AlphaDB、GUI、任务系统、本机天软客户端或 pyTSL 登录会话。

当前版本：`1.1.0`。1.1 在 1.0 的基础信息、披露明细、基金持仓和跨资产元数据之上，新增了批量 `markettable` 行情层，以及天软数据字典可确认的基金净值、基金份额、股票财报、业绩预告/快报和一批股票事件接口。

## 安装

开发安装：

```bash
cd tinydata
pip install -e ".[test]"
```

## 配置

显式配置：

```python
import tinydata as td

td.configure(
    user="your_user",
    password="your_password",
    opi_url="https://opi.tinysoft.com.cn",
    opi_auth_mode="basic",
    timeout_ms=60000,
)
```

也可以使用环境变量或 `~/.tinydata/config.toml`。常用环境变量：

```text
TINYDATA_USER
TINYDATA_PASSWORD
TINYDATA_OPI_URL
TINYDATA_OPI_AUTH_MODE
TINYDATA_OPI_SESSION_KEY
TINYDATA_OPI_SESSION_PASSWORD
TINYDATA_OPI_RUN_FUNC_NAME
TINYDATA_OPI_QUERY_FUNC_NAME
TINYDATA_CACHE_DIR
TINYDATA_CODE_DIR
```

SESSION-KEY / API-KEY 租户如果不能直接调用 `/Service/Run/`，需要在天软侧提供 run/query wrapper，并配置 `run_func_name` / `query_func_name`。

## 代码池

`codes=None` 时，tinydata 1.0 会优先通过 OPI 基础表自动构建代码池并缓存到本机 parquet。显式传入 `codes` 时永远优先使用用户传入代码。

本地 CSV 只作为 OPI 代码池不可用时的兜底，默认目录：

```text
~/.tinydata/codes/
```

示例 `~/.tinydata/codes/fund.csv`：

```csv
ts_code
000001.OF
000002.OF
```

## 接口

元数据：

```python
td.list_datasets(domain=None, priority=None)
td.get_dataset_info("fund_fof_holding_detail")
```

代码池：

```python
td.stock_codes()
td.fund_codes()
td.fof_fund_codes()
td.bond_codes()
td.index_codes()
td.future_codes()
td.option_codes(trade_date="20240517")
td.market_codes()
```

P0/P1/selected P2 数据集已按领域导出：

```python
# 行情
td.query_market_panel(codes=["000001.SZ", "600000.SH"], start_date="20260520", end_date="20260522", cycle="日线")
td.stock_daily(codes=["000001.SZ"], start_date="20260520", end_date="20260522")
td.stock_weekly(codes=["000001.SZ"], start_date="20260101", end_date="20260522")
td.stock_monthly(codes=["000001.SZ"], start_date="20250101", end_date="20260522")
td.fund_daily(codes=["510300.SH"], start_date="20260520", end_date="20260522")
td.index_daily(codes=["000300.CSI"], start_date="20260520", end_date="20260522")
td.cbond_daily(codes=["113001.SH"], start_date="20260520", end_date="20260522")
td.future_daily(codes=["IF2606"], start_date="20260520", end_date="20260522")
td.option_daily(codes=["10000001.SH"], start_date="20260520", end_date="20260522")

# 基金
td.fund_basic_ext()
td.fund_manager_ext(start_date="20240101", end_date="20241231")
td.fund_nav(codes=["000001.OF"], start_date="20240501", end_date="20240531")
td.fund_share(codes=["000001.OF"], start_date="20240101", end_date="20241231")
td.fund_stock_holding_detail(report_period="20231231")
td.fund_bond_holding_detail(report_period="20231231")
td.fund_fof_holding_detail(report_period="20231231")
td.fund_asset_alloc(report_period="20231231")
td.fund_classification_info(refresh=True)

# 股票
td.stock_basic_ext()
td.stock_suspend(start_date="20240101", end_date="20241231")
td.stock_fina_pit_ext(start_date="20240101", end_date="20241231")
td.fina_income(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.fina_balancesheet(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.fina_cashflow(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.fina_indicator(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.fina_forecast(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.fina_express(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.fina_disclosure(codes=["000001.SZ"], report_period="20241231")
td.fina_mainbz(codes=["000001.SZ"], report_period="20241231")
td.stock_dividend(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.stock_sharefloat(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.stock_holdernumber(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.stock_blocktrade(codes=["000001.SZ"], trade_date="20240517")
td.stock_margin(trade_date="20240517")
td.stock_margindetail(codes=["000001.SZ"], trade_date="20240517")
td.stock_hsgt_daily(trade_date="20240517")
td.stock_lending_balance(trade_date="20240517")
td.stock_pledge_detail(start_date="20240101", end_date="20241231")

# 跨资产
td.trade_calendar(start_date="20240101", end_date="20241231")
td.index_basic_ext()
td.index_member_versioned(codes=["000300.CSI"], all_history=True)
td.market_calendar_multi(start_date="20240101", end_date="20241231")
td.bond_basic_ext()
td.future_basic_ext()
td.future_product_mapping_ext()
td.option_basic_daily_ext(trade_date="20240517")
```

高容量明细表默认需要传 `report_period`、`trade_date`、`start_date/end_date`，或显式设置 `all_history=True`。

## 1.1 范围边界

以下接口暂未作为稳定 API 暴露：

- `stock_adjfactor`、`fund_adjfactor`、`stock_dailybasic`、`index_dailybasic`：尚未在天软数据字典中确认稳定等价 InfoTable 表或 markettable 字段。
- `index_weight`：数据字典给出的提取方式是 `GetBkWeightByDate`，不是普通 InfoTable；需要单独验证函数签名和返回结构后再进入稳定 API。
- 分钟线和派生特征：不进入 1.1 稳定主 API。

## 缓存

业务接口默认使用本机 parquet 缓存：

```text
~/.tinydata/cache/
```

`refresh=False` 时优先读缓存；`refresh=True` 时重新请求天软并覆盖缓存。缓存 key 包含 dataset、table_id、字段版本、日期参数、代码池 hash 和字段列表。

## 测试

不需要天软账号的单元测试：

```bash
cd tinydata
python -m pytest
```

真实天软连接测试使用 `requires_tinysoft` 标记，默认不运行。

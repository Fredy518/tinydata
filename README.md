# tinydata

`tinydata` 是一个基于天软 TS-OPI 的轻量级直连数据接口包。它是独立 Python library，运行时不依赖 AlphaHome、AlphaDB、GUI、任务系统、本机天软客户端或 pyTSL 登录会话。

当前版本：`1.1.0`。

- **详细使用文档**：[docs/usage.md](docs/usage.md)

---

## 快速开始

```python
import tinydata as td

# 1. 配置认证（也可通过环境变量或配置文件，见下文）
td.configure(user="your_user", password="your_password")

# 2. 拉取股票日线（自动使用缓存）
df = td.stock_daily(codes=["000001.SZ", "600000.SH"],
                    start_date="20260101", end_date="20260131")
print(df.head())

# 3. 拉取基金净值
df = td.fund_nav(codes=["000001.OF"], start_date="20240101", end_date="20241231")
```

---

## 安装

```bash
# 开发安装（含测试依赖）
cd tinydata
pip install -e ".[test]"

# 生产安装
pip install tinydata
```

**依赖**：Python ≥ 3.9，pandas ≥ 2.2，pyarrow ≥ 15，pydantic ≥ 2，platformdirs ≥ 4，python-dateutil ≥ 2.8。

---

## 配置

配置优先级（从高到低）：`td.configure()` 显式调用 → 环境变量 → `~/.tinydata/config.toml` → 内置默认值。

### 代码配置

```python
import tinydata as td

td.configure(
    user="your_user",
    password="your_password",
    opi_url="https://opi.tinysoft.com.cn",   # 默认值，可省略
    opi_auth_mode="basic",                    # basic / bearer / x-api-key
    timeout_ms=60000,                         # 单次请求超时（毫秒）
    request_interval=0.2,                     # 请求间隔（秒），限流保护
    cache_dir="~/.tinydata/cache",            # 缓存目录
)
```

### 环境变量

| 环境变量 | 说明 |
|---|---|
| `TINYDATA_USER` | 天软账号 |
| `TINYDATA_PASSWORD` | 天软密码 |
| `TINYDATA_OPI_URL` | OPI 地址，默认 `https://opi.tinysoft.com.cn` |
| `TINYDATA_OPI_AUTH_MODE` | 认证模式：`basic` / `bearer` / `x-api-key` |
| `TINYDATA_OPI_SESSION_KEY` | SESSION-KEY / API-KEY 租户的密钥 |
| `TINYDATA_OPI_SESSION_PASSWORD` | SESSION-KEY 密钥密码（可选） |
| `TINYDATA_OPI_RUN_FUNC_NAME` | SESSION-KEY 租户的 run wrapper 函数名 |
| `TINYDATA_OPI_QUERY_FUNC_NAME` | SESSION-KEY 租户的 query wrapper 函数名 |
| `TINYDATA_TIMEOUT_MS` | 请求超时（毫秒） |
| `TINYDATA_REQUEST_INTERVAL` | 请求间隔（秒） |
| `TINYDATA_CACHE_DIR` | 本地缓存目录 |
| `TINYDATA_CODE_DIR` | 本地代码池 CSV 目录 |

### 配置文件

`~/.tinydata/config.toml`（支持 `[tinydata]` 节或顶层 key）：

```toml
[tinydata]
user = "your_user"
password = "your_password"
opi_url = "https://opi.tinysoft.com.cn"
opi_auth_mode = "basic"
timeout_ms = 60000
```

---

## 认证模式

| `opi_auth_mode` | 适用场景 | 所需配置 |
|---|---|---|
| `basic`（默认） | 开发者账号，直接用户名密码 | `user` + `password` |
| `bearer` / `session` | SESSION-KEY 租户 | `session_key`（+可选 `session_password`） |
| `x-api-key` / `api-key` | API-KEY 租户 | `session_key` |

SESSION-KEY / API-KEY 租户若无法直接调用 `/Service/Run/`，需在天软侧部署 run/query wrapper，并配置 `run_func_name` / `query_func_name`。

---

## 代码池（Universe）

`codes=None` 时，dataset API 自动通过 OPI 基础表构建代码池并缓存到本地 parquet；显式传入 `codes` 时始终优先使用用户代码。

### 代码池函数

```python
td.stock_codes()                              # A 股
td.fund_codes()                               # 开放式基金
td.fof_fund_codes()                           # FOF 基金
td.bond_codes()                               # 债券
td.index_codes()                              # 指数
td.future_codes()                             # 期货合约
td.option_codes(trade_date="20240517")        # 期权合约（需传交易日）
td.market_codes()                             # 市场日历代码
```

所有代码池函数支持 `refresh=True` 强制重新从 OPI 拉取并更新缓存。

### 本地 CSV 兜底

OPI 代码池不可用时，会回退到本地 CSV（默认目录 `~/.tinydata/codes/`）：

```
~/.tinydata/codes/
    stock.csv
    fund.csv
    fof_fund.csv
    bond.csv
    index.csv
    future.csv
```

CSV 格式（需包含 `ts_code`、`code` 或 `symbol` 列之一）：

```csv
ts_code
000001.OF
000002.OF
```

---

## 缓存

所有数据集接口默认使用本地 parquet 缓存（`~/.tinydata/cache/`）。

```python
# 使用缓存（默认）
df = td.stock_daily(codes=["000001.SZ"], start_date="20260101", end_date="20260131")

# 强制刷新，忽略缓存
df = td.stock_daily(codes=["000001.SZ"], start_date="20260101", end_date="20260131",
                    refresh=True)
```

缓存 key 由 dataset 名称、table_id、字段版本、日期参数、代码池 hash 等确定，参数变化会自动命中不同缓存条目。

---

## 数据集 API

所有 dataset 函数均通过 `td.<function_name>(...)` 调用，返回 `pandas.DataFrame`。  
详细参数说明见 [docs/usage.md](docs/usage.md)。

### 元数据

```python
td.list_datasets()                            # 列出所有数据集（含 domain、priority、table_id）
td.list_datasets(domain="fund")               # 按领域筛选
td.list_datasets(priority="P0")               # 按优先级筛选
td.get_dataset_info("fund_fof_holding_detail")# 单个数据集详情
```

### 行情（market）

```python
# 多资产批量行情（通用）
td.query_market_panel(codes=["000001.SZ"], start_date="20260101", end_date="20260131", cycle="日线")

# 股票
td.stock_daily(codes=["000001.SZ"], start_date="20260101", end_date="20260131")
td.stock_weekly(codes=["000001.SZ"], start_date="20260101", end_date="20260522")
td.stock_monthly(codes=["000001.SZ"], start_date="20250101", end_date="20260522")

# 基金 / 指数 / 可转债 / 期货 / 期权 / 港股
td.fund_daily(codes=["510300.SH"], start_date="20260101", end_date="20260131")
td.index_daily(codes=["000300.CSI"], start_date="20260101", end_date="20260131")
td.cbond_daily(codes=["113001.SH"], start_date="20260101", end_date="20260131")
td.future_daily(codes=["IF2606"], start_date="20260101", end_date="20260131")
td.option_daily(codes=["10000001.SH"], start_date="20260101", end_date="20260131")
td.hk_daily(codes=["00700.HK"], start_date="20260101", end_date="20260131")
```

行情接口默认返回字段：`trade_date`、`tsl_code`、`open`、`high`、`low`、`close`、`volume`、`amount`。

### 基金（fund）

```python
# 基础信息 / 管理人
td.fund_basic_ext()                                     # 全量基金基本信息
td.fund_basic()                                         # `fund_basic_ext` 的别名
td.fund_manager()                                       # 基金经理任职
td.fund_manager_ext(start_date="20240101", end_date="20241231")

# 净值 / 份额
td.fund_nav(codes=["000001.OF"], start_date="20240101", end_date="20241231")
td.fund_share(codes=["000001.OF"], start_date="20240101", end_date="20241231")

# 持仓
td.fund_stock_holding_detail(report_period="20231231")
td.fund_stock_holding(codes=["000001.OF"], report_period="20231231")
td.fund_bond_holding_detail(report_period="20231231")
td.fund_bond_holding(codes=["000001.OF"], report_period="20231231")
td.fund_fof_holding_detail(report_period="20231231")
td.fund_cbond_holding_detail(report_period="20231231")
td.fund_abs_holding_detail(report_period="20231231")

# 资产配置 / 行业配置 / 债券配置
td.fund_asset_alloc(report_period="20231231")
td.fund_industry_alloc(codes=["000001.OF"], report_period="20231231")
td.fund_bond_alloc(codes=["000001.OF"], report_period="20231231")

# 分类 / 份额持有人 / 前十大持有人 / 经纪商席位
td.fund_classification_info()
td.fund_classification_member()
td.fund_holder_structure(codes=["000001.OF"], report_period="20231231")
td.fund_top_holder(codes=["000001.OF"], report_period="20231231")
td.fund_broker_seat(codes=["000001.OF"], start_date="20240101", end_date="20241231")

# 季报财务
td.fund_financial_quarterly_ext(codes=["000001.OF"], report_period="20231231")
```

### 股票（stock）

```python
# 基础信息 / 上市状态
td.stock_basic_ext()
td.stock_suspend(start_date="20240101", end_date="20241231")
td.stock_namechange(codes=["000001.SZ"])

# 财务（InfoTable，按代码+日期查询）
td.stock_fina_pit_ext(start_date="20240101", end_date="20241231")  # PIT 披露日历
td.fina_income(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.fina_balancesheet(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.fina_cashflow(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.fina_indicator(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.fina_forecast(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.fina_express(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.fina_disclosure(codes=["000001.SZ"], report_period="20241231")
td.fina_mainbz(codes=["000001.SZ"], report_period="20241231")
td.fina_mainbz_area(codes=["000001.SZ"], report_period="20241231")
td.fina_mainbz_industry(codes=["000001.SZ"], report_period="20241231")
td.fina_mainbz_product(codes=["000001.SZ"], report_period="20241231")

# 股东 / 股权
td.stock_dividend(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.stock_sharefloat(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.stock_holdernumber(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.stock_holder_change_ext(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.stock_unlock_schedule(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.stock_repurchase_ext(codes=["000001.SZ"], start_date="20240101", end_date="20241231")

# 行业
td.stock_industry_versioned(codes=["000001.SZ"])

# 交易事件
td.stock_blocktrade(codes=["000001.SZ"], trade_date="20240517")
td.stock_public_trade_info(codes=["000001.SZ"], trade_date="20240517")

# 融资融券 / 借贷
td.stock_margin(trade_date="20240517")
td.stock_margindetail(codes=["000001.SZ"], trade_date="20240517")
td.stock_margin_collateral(trade_date="20240517")
td.stock_lending_balance(trade_date="20240517")
td.stock_lending_summary(trade_date="20240517")
td.stock_lending_trade(codes=["000001.SZ"], trade_date="20240517")

# 沪深港通
td.stock_hsgt_daily(trade_date="20240517")
td.stock_hsgt_hold(codes=["000001.SZ"], trade_date="20240517")
td.stock_hsgt_short_balance(trade_date="20240517")
td.stock_hsgt_top10(trade_date="20240517")

# 质押
td.stock_pledge_detail(start_date="20240101", end_date="20241231")
td.stock_pledge_balance(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.stock_pledge_rate(start_date="20240101", end_date="20241231")    # 市场级汇总
td.stock_pledge_summary(start_date="20240101", end_date="20241231")
```

### 跨资产（cross-asset）

```python
# 交易日历
td.trade_calendar(start_date="20240101", end_date="20241231")
td.market_calendar_multi(start_date="20240101", end_date="20241231")

# 指数
td.index_basic_ext()
td.index_member_versioned(codes=["000300.CSI"], all_history=True)

# 债券
td.bond_basic_ext()

# 期货
td.future_basic_ext()
td.future_product_mapping_ext()

# 期权
td.option_basic_daily_ext(trade_date="20240517")
```

---

## 错误处理

```python
import tinydata as td
from tinydata import (
    TinyDataError,          # 基类
    TinyDataAuthError,      # 认证失败（用户名/密码/session_key 问题）
    TinyDataConfigError,    # 配置无效或缺失
    TinyDataQueryError,     # OPI 查询失败（HTTP 错误、TSL 执行错误）
    TinyDataTimeoutError,   # 请求超时
    TinyDataCodePoolError,  # 代码池为空且无兜底
    TinyDataParameterError, # 缺少必要的查询安全参数
)

try:
    df = td.stock_daily(codes=["000001.SZ"], start_date="20260101", end_date="20260131")
except TinyDataAuthError as e:
    print("认证失败，检查用户名/密码:", e)
except TinyDataTimeoutError as e:
    print("请求超时，可增大 timeout_ms:", e)
except TinyDataParameterError as e:
    print("缺少参数（高容量表需要 start_date/end_date 或 all_history=True）:", e)
except TinyDataError as e:
    print("其他 tinydata 错误:", e)
```

---

## 1.1 范围边界

以下接口暂未作为稳定 API 暴露：

- `stock_adjfactor`、`fund_adjfactor`、`stock_dailybasic`、`index_dailybasic`：尚未在天软数据字典中确认稳定等价 InfoTable 表或 markettable 字段。
- `index_weight`：数据字典给出的提取方式是 `GetBkWeightByDate`，不是普通 InfoTable；需要单独验证函数签名和返回结构后再进入稳定 API。
- 分钟线和派生特征：不进入 1.1 稳定主 API。

---

## 测试

不需要天软账号的单元测试：

```bash
cd tinydata
python -m pytest
```

真实天软连接测试使用 `requires_tinysoft` 标记，默认不运行：

```bash
python -m pytest -m requires_tinysoft
```

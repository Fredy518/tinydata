# tinydata

`tinydata` 是一个基于天软 TS-OPI 的轻量级直连数据接口包。它是独立 Python library，运行时不依赖 AlphaHome、AlphaDB、GUI、任务系统、本机天软客户端或 pyTSL 登录会话。

当前版本：`1.2.1`。

`1.2.1` 在 `1.2.0` 的并行查询与进度条能力之上，继续把共享日期解析、代码转换、future/option 合约后处理与 universe 代码池提取下沉为向量化实现。对 market、InfoTable-backed 数据集、自定义 TSL 函数接口和代码池函数，大批量查询时本地规范化尾耗时会明显下降。

- **详细使用文档**：[docs/usage.md](docs/usage.md)
- **天软 FAQ/远端资料审计**：[docs/tinysoft_faq_audit.md](docs/tinysoft_faq_audit.md)、[docs/tinysoft_stock_fund_reference_audit.md](docs/tinysoft_stock_fund_reference_audit.md)

---

## 快速开始

推荐先把认证信息放到环境变量中，代码里只保留查询逻辑。

```powershell
# PowerShell
$env:TINYDATA_USER = "your_user"
$env:TINYDATA_PASSWORD = "your_password"
```

```python
import tinydata as td

# 1. 拉取股票日线（自动使用缓存）
df = td.stock_daily(codes=["000001.SZ", "600000.SH"],
                    start_date="20260101", end_date="20260131")
print(df.head())

# 2. 拉取基金净值
df = td.fund_nav(codes=["000001.OF"], start_date="20240101", end_date="20241231")
```

如果你使用 bash/zsh，可改用 `export TINYDATA_USER=...` 和 `export TINYDATA_PASSWORD=...`。

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

推荐把账号、密钥和常用运行参数配置到环境变量中；`td.configure()` 更适合 notebook、测试或一次性脚本里做临时覆盖。

### 推荐：环境变量配置

```powershell
# PowerShell
$env:TINYDATA_USER = "your_user"
$env:TINYDATA_PASSWORD = "your_password"
$env:TINYDATA_OPI_URL = "https://opi.tinysoft.com.cn"
$env:TINYDATA_OPI_AUTH_MODE = "basic"
$env:TINYDATA_TIMEOUT_MS = "60000"
$env:TINYDATA_REQUEST_INTERVAL = "0.2"
```

```bash
# bash / zsh
export TINYDATA_USER="your_user"
export TINYDATA_PASSWORD="your_password"
export TINYDATA_OPI_URL="https://opi.tinysoft.com.cn"
export TINYDATA_OPI_AUTH_MODE="basic"
export TINYDATA_TIMEOUT_MS="60000"
export TINYDATA_REQUEST_INTERVAL="0.2"
```

代码中直接使用：

```python
import tinydata as td

df = td.stock_daily(codes=["000001.SZ"], start_date="20260101", end_date="20260131")
```

### 临时代码配置（覆盖环境变量）

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

### 环境变量清单

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
td.fund_market_codes()                        # 上市交易基金/ETF/LOF 行情代码
td.fof_fund_codes()                           # FOF 基金
td.bond_codes()                               # 债券
td.index_codes()                              # 指数
td.future_codes()                             # 期货合约
td.option_codes(trade_date="20240517")        # 期权合约（需传交易日）
td.market_codes()                             # 市场日历代码（含 A 股、期货、港股、沪深港通、银行间债券）
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
# stock_daily 在 codes=None 时默认使用当前活跃 A 股股票池；
# 如需包含退市历史股票，请显式传 td.stock_codes(include_inactive=True)
td.stock_daily(codes=["000001.SZ"], start_date="20260101", end_date="20260131")
td.stock_weekly(codes=["000001.SZ"], start_date="20260101", end_date="20260522")
td.stock_monthly(codes=["000001.SZ"], start_date="20250101", end_date="20260522")

# 全市场历史行情可配合较小 code_batch_size 和 max_workers 并行抓取多个代码批次
td.stock_daily(start_date="20260101", end_date="20260131", code_batch_size=100, max_workers=4)

# 需要观察批次进度时，可显式开启 progress
td.stock_daily(start_date="20260101", end_date="20260131", code_batch_size=100, max_workers=4, progress=True)

# 股票复权行情：adjust=1/ratio 为比例复权，adjust=2/complex 为复杂复权
td.stock_daily(codes=["000001.SZ"], start_date="20260101", end_date="20260131",
               adjust="complex", adjust_date="20260131")

# 基金 / 指数 / 可转债 / 期货 / 期权 / 港股
# fund_daily 在 codes=None 时默认使用 fund_market_codes()，避免用开放式基金 OF 全集请求行情
td.fund_daily(codes=["510300.SH"], start_date="20260101", end_date="20260131")
td.index_daily(codes=["000300.CSI"], start_date="20260101", end_date="20260131")
td.cbond_daily(codes=["113001.SH"], start_date="20260101", end_date="20260131")
td.future_daily(codes=["IF2606"], start_date="20260101", end_date="20260131")
td.option_daily(codes=["10000001.SH"], start_date="20260101", end_date="20260131")
td.hk_daily(codes=["00700.HK"], start_date="20260101", end_date="20260131")
```

行情接口默认返回字段：`trade_date`、`tsl_code`、`open`、`high`、`low`、`close`、`volume`、`amount`。

复权参数按天软 `pn_rate()` 语义透传：`adjust=0` 不复权，`adjust=1` 比例复权（交易所数据除权，只考虑比例关系），`adjust=2` 复杂复权（分红送配数据除权，同时考虑送股比例和现金分红等加减关系）。`adjust_date` 写入 `Pn_rateday()`，表示复权价格锚定到哪一天：`adjust_date=0` 为天软当前/最后口径，通常用于前复权；`adjust_date=-1` 为上市日/成立日口径，通常用于后复权；指定具体日期则是定点复权。传入 `adjust` 但不传 `adjust_date` 时，tinydata 默认以本次查询 `end_date`/`trade_date` 作为 `Pn_rateday()`，即默认更接近常用前复权。

全市场历史行情若需要加速，建议组合使用较小的 `code_batch_size`（如 50~150）与 `max_workers>1` 并行抓取多个代码批次；如果 OPI 租户容易触发 429，请同步降低 `max_workers` 或增大 `request_interval`。并行批次若仍返回 429，tinydata 会自动降低 `max_workers` 并重试失败批次。`progress=None` 时，交互式环境默认开启进度条，脚本环境默认关闭；显式传 `progress=True/False` 可覆盖默认行为。终端里会显示 tqdm 风格进度条，IPython/Jupyter 会优先显示 notebook 友好的进度条；若环境缺少 tqdm，则回退到文本进度条。

重型 InfoTable 数据集也支持同样的并行和进度参数，例如股票财务链、基金净值/持仓/配置链：

```python
td.fina_indicator(
    start_date="20240101",
    end_date="20241231",
    code_batch_size=120,
    max_workers=4,
    progress=True,
)

td.fund_stock_holding_detail(
    report_period="20240630",
    code_batch_size=300,
    max_workers=4,
    progress=True,
)
```

### 基金（fund）

```python
# 基础信息 / 管理人
td.fund_basic_ext()                                     # 全量基金基本信息
td.fund_basic()                                         # `fund_basic_ext` 的别名
td.fund_manager()                                       # 基金经理任职
td.fund_manager_ext(start_date="20240101", end_date="20241231")

# 净值 / 份额
td.fund_nav(codes=["000001.OF"], start_date="20240101", end_date="20241231")
td.fund_adjusted_nav(codes=["510050.OF"], start_date="20190101", end_date="20190425", adjust=1)  # 复权净值
td.fund_share(codes=["000001.OF"], start_date="20240101", end_date="20241231")
td.fund_benchmark(codes=["502049.SH"])                         # 业绩比较基准明细
td.fund_fee(codes=["502004.SH"])                               # 开放式基金费率
td.fund_nav_benchmark_return(codes=["000814.OF"], report_period="20231231")

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

# 定报财务 / 分红拆分 / ETF PCF
td.fund_financial_quarterly_ext(codes=["000001.OF"], report_period="20231231")
td.fund_balance_sheet(codes=["004905.OF"], report_period="20231231")
td.fund_income_statement(codes=["160127.OF"], report_period="20231231")
td.fund_buy_sell(codes=["004905.OF"], report_period="20231231")
td.fund_dividend(codes=["000001.OF"], start_date="20200101", end_date="20241231")
td.fund_split(codes=["160127.OF"], all_history=True)
td.fund_namechange(codes=["000001.OF"])
td.fund_etf_sub_redemption(codes=["159901.OF"], start_date="20100701", end_date="20100803")
td.fund_etf_constituent(codes=["510050.OF"], trade_date="20190816")

# 自定义 TSL 函数接口也支持按代码并行和进度条
td.fund_adjusted_nav(
    codes=["510050.OF", "159915.OF"],
    start_date="20190101",
    end_date="20190425",
    adjust=1,
    max_workers=4,
    progress=True,
)
td.fund_etf_constituent(codes=["510050.OF", "159915.OF"], trade_date="20190816", max_workers=4, progress=True)
```

基金定期报告类表遵循天软文档的取数代码规则：A/B/C 等不同收费份额多数需要映射到“不同收费模式基金主代码”，分级基金需要映射到“母基金代码”。tinydata 会对已确认的定报接口自动做该映射；返回的 `tsl_code` 是实际用于取数的主代码/母基金代码。

财务和基金定报查询中，`report_period` 只过滤报告期；如需表达“某报告期截至某披露时点可见”，请同时传 `as_of_date`，例如 `td.fina_indicator(codes=["000001.SZ"], report_period="20231231", as_of_date="20240430")`。

`fund_adjusted_nav`、`fund_etf_constituent`、`index_member_snapshot`、`index_weight` 这类自定义 TSL 函数接口按代码逐个请求，不使用 `code_batch_size`；需要加速多代码查询时，直接传 `max_workers>1` 即可。若并行请求触发 429，tinydata 会自动降低 `max_workers` 并重试失败代码。`progress=None` 时交互式环境默认开启、脚本环境默认关闭；启用后会显示环境感知的代码级进度条，在 IPython/Jupyter 中优先使用 notebook 友好展示。

### 股票（stock）

```python
# 基础信息 / 上市状态
td.stock_basic_ext()
td.stock_ipo(codes=["000001.SZ"])
td.stock_suspend(start_date="20240101", end_date="20241231")
td.stock_namechange(codes=["000001.SZ"])
td.stock_delist_solution(codes=["600087.SH"], all_history=True)
td.stock_trade_time(codes=["000001.SH"], all_history=True)       # 证券品种交易时间

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
td.stock_top10_holder(codes=["000001.SZ"], report_period="20231231")
td.stock_top10_float_holder(codes=["000001.SZ"], report_period="20231231")
td.stock_controller(codes=["000001.SZ"], report_period="20231231")
td.stock_officer_hold_change(codes=["000001.SZ"], start_date="20200101", end_date="20241231")
td.stock_foreign_holding(codes=["603605.SH"], start_date="20240101", end_date="20241231")
td.stock_holder_change_ext(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.stock_unlock_schedule(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.stock_repurchase_ext(codes=["000001.SZ"], start_date="20240101", end_date="20241231")
td.stock_nonrecurring(codes=["000001.SZ"], report_period="20231231")

# 行业
td.stock_classification_info(codes=["SWHY"], all_history=True)   # 行业/分类属性代码
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
td.index_member_snapshot(codes=["000300.CSI"], trade_date="20210107")   # 指定日成份股快照
td.index_weight(codes=["000300.CSI"], trade_date="20210531")            # 指定日成份权重
td.index_member_snapshot(codes=["000300.CSI", "000905.CSI"], trade_date="20210107", max_workers=4, progress=True)
td.index_weight(codes=["000300.CSI", "000905.CSI"], trade_date="20210531", max_workers=4, progress=True)

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
    TinyDataRateLimitError, # OPI 429：并发/请求数超限，自动重试后仍失败
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
except TinyDataRateLimitError as e:
    print("OPI 并发或请求数超限，稍后重试或降低并发:", e)
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
- `fund_adjusted_nav`：天软 FAQ 给出的稳定方式是 `FundNAWByRateBegtEndt`，不是普通 `基金.净值` 表；需要单独封装和验证后再进入稳定 API。
- `tradetable`、盘口、Level 2、集合竞价、夜盘高频下载：属于高容量行情接口，进入稳定 API 前需要单独的分页、限流和字段说明。
- 股票自由流通类数据：TSDN 2025-11-25 文档说明需联系商务授权，暂不作为默认稳定接口暴露。
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

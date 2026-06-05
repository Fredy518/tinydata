# tinydata 使用手册

> tinydata v1.2.2 — 轻量级天软 TS-OPI 数据客户端

`1.2.2` 新增 `td.realtime_bar()` 与 `td.realtime_snapshot()` 实时/近实时行情接口，并对 OPI 429 并发/请求数超限增加专门异常与自动退避重试。

## 目录

1. [安装与配置](#1-安装与配置)
2. [代码池（证券宇宙）](#2-代码池证券宇宙)
3. [市场行情数据](#3-市场行情数据)
4. [股票数据](#4-股票数据)
5. [基金数据](#5-基金数据)
6. [债券数据](#6-债券数据)
7. [指数与交易日历](#7-指数与交易日历)
8. [期货数据](#8-期货数据)
9. [期权数据](#9-期权数据)
10. [TinyClient 直接接口](#10-tinyclient-直接接口)
11. [错误处理](#11-错误处理)
12. [缓存管理](#12-缓存管理)
13. [查询参数约定](#13-查询参数约定)
14. [开发与测试](#14-开发与测试)

---

## 1 安装与配置

### 安装

```bash
pip install tinydata
# 或开发模式
pip install -e ".[test]"
```

### 最小示例

```python
import tinydata as td

td.configure(
    user="user",
    password="pass",
    opi_url="http://your-opi-host:8888",
)

# 获取所有A股代码
codes = td.stock_codes()

# 拉取日行情
df = td.stock_daily(codes=codes[:50], start_date="2024-01-01", end_date="2024-03-31")
print(df.head())
```

### 配置优先级

`td.configure()` > 环境变量 > `~/.tinydata/config.toml` > 内置默认值

| 参数 | 环境变量 | 默认值 | 说明 |
|------|---------|--------|------|
| `user` | `TINYDATA_USER` | `""` | 天软用户名 |
| `password` | `TINYDATA_PASSWORD` | `""` | 天软密码 |
| `host` | `TINYDATA_HOST` | `tsl.tinysoft.com.cn` | 低层连接主机 |
| `port` | `TINYDATA_PORT` | `443` | 低层连接端口 |
| `ini_path` | `TINYDATA_INI` | `""` | 天软 ini 路径 |
| `opi_url` | `TINYDATA_OPI_URL` / `TINYSOFT_OPI_URL` | `https://opi.tinysoft.com.cn` | OPI 服务地址 |
| `opi_auth_mode` | `TINYDATA_OPI_AUTH_MODE` / `TINYSOFT_OPI_AUTH_MODE` | `basic` | `basic` / `bearer` / `session` / `session-key` / `x-api-key` / `api-key` |
| `session_key` | `TINYDATA_OPI_SESSION_KEY` / `TINYDATA_SESSION_KEY` | `""` | Session/API key |
| `session_password` | `TINYDATA_OPI_SESSION_PASSWORD` / `TINYDATA_SESSION_PASSWORD` | `""` | Session/API key 密码 |
| `service` | `TINYDATA_SERVICE` / `TINYSOFT_SERVICE` | `""` | 服务名 |
| `json_encode` | `TINYDATA_OPI_JSON_ENCODE` / `TINYSOFT_OPI_JSON_ENCODE` | `utf8` | OPI 编码方式 |
| `run_func_name` | `TINYDATA_OPI_RUN_FUNC_NAME` / `TINYSOFT_OPI_RUN_FUNC_NAME` | `""` | run wrapper 名称 |
| `query_func_name` | `TINYDATA_OPI_QUERY_FUNC_NAME` / `TINYSOFT_OPI_QUERY_FUNC_NAME` | `""` | query wrapper 名称 |
| `cache_dir` | `TINYDATA_CACHE_DIR` | `~/.tinydata/cache` | 本地缓存目录 |
| `code_dir` | `TINYDATA_CODE_DIR` | `~/.tinydata/codes` | 本地代码池 CSV 目录 |
| `request_interval` | `TINYDATA_REQUEST_INTERVAL` | `0.2` | 请求间隔（秒） |
| `timeout_ms` | `TINYDATA_TIMEOUT_MS` | `60000` | HTTP 超时（毫秒） |

### 认证模式

| 模式 | 所需参数 | 请求头 | 说明 |
|------|---------|--------|------|
| `basic` | `user` + `password` | HTTP Basic Auth | 默认模式 |
| `bearer` / `session` / `session-key` | `session_key`（可选 `session_password`） | `Authorization: Bearer <key>` | Session 模式 |
| `x-api-key` / `api-key` | `session_key`（可选 `session_password`） | `X-API-Key: <key>` | API key 模式 |

### config.toml 示例

```toml
[tinydata]
user = "myuser"
password = "mypassword"
opi_url = "http://192.168.1.100:8888"
opi_auth_mode = "basic"
timeout_ms = 60000
request_interval = 0.2
cache_dir = "~/.tinydata/cache"
```

---

## 2 代码池（证券宇宙）

代码池函数返回 tinysoft 格式代码（如 `SZ000001`）。数据集函数的 `codes=` 参数可以直接传入这些列表。

### 通用参数

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `refresh` | bool | False | 强制刷新，忽略本地缓存 |
| `include_inactive` | bool | True | 适用于 `stock_codes` / `fund_codes` / `fund_market_codes` / `bond_codes` / `index_codes` / `future_codes` / `option_codes`，`False` 时尽量过滤退市、停用或失效代码 |

### stock_codes — A股代码

```python
codes = td.stock_codes(
    include_inactive=False,  # 只保留当前状态包含“上市/正常/交易”的股票
    refresh=False,
)
# 返回: List[str]，如 ["SZ000001", "SH600000", ...]
```

> `stock_codes()` 的默认值是 `include_inactive=True`，会尽量返回全量代码；传 `include_inactive=False` 才会过滤非活跃标的。

### fund_codes — 基金代码

```python
codes = td.fund_codes(include_inactive=False, refresh=False)
# 返回: List[str]，如 ["OF000001", "OF000002", ...]
```

### fund_market_codes — 上市交易基金行情代码

```python
codes = td.fund_market_codes(include_inactive=False, refresh=False)
# 返回: List[str]，如 ["SH510050", "SZ159919", ...]
```

### fof_fund_codes — FOF 基金代码

```python
codes = td.fof_fund_codes(refresh=False)
# 返回: List[str]
```

### bond_codes — 债券代码

```python
codes = td.bond_codes(include_inactive=False, refresh=False)
# 返回: List[str]
```

### index_codes — 指数代码

```python
codes = td.index_codes(include_inactive=False, refresh=False)
# 返回: List[str]，如 ["SH000001", "SZ399001", ...]
```

### future_codes — 期货代码

```python
codes = td.future_codes(include_inactive=False, refresh=False)
# 返回: List[str]
```

### option_codes — 期权代码

```python
codes = td.option_codes(
    trade_date=None,       # 指定某日（推荐，结果更准确）
    start_date=None,
    end_date=None,
    include_inactive=True,
    refresh=False,
)
# 返回: List[str]
```

> `option_codes()` 建议传入 `trade_date`，否则返回当前所有合约（可能包含已过期）。

### market_codes — 市场代码

```python
codes = td.market_codes()
# 返回固定列表: ["SH000001", "SZ399001", "QI000001", "HKHSI001", "HSG000001", "HSG000002", "CBICBA00301"]
```

### 代码解析优先级

数据集函数内部按如下顺序获取代码池：

1. **显式传入** `codes=["SZ000001", ...]`
2. **本地 parquet 缓存** `~/.tinydata/cache/universe/<name>/<sha256>.parquet`
3. **OPI 实时查询** 对应的 universe 函数
4. **本地 CSV** `~/.tinydata/codes/<name>.csv`
5. 以上均失败 → `TinyDataCodePoolError`

---

## 3 市场行情数据

市场行情通过 `query_market_panel()` 批量拉取，或直接调用各资产类别的快捷函数。

### query_market_panel — 批量行情

```python
df = td.query_market_panel(
    symbols=None,             # 位置参数，等价于 codes
    codes=None,               # 代码列表（None = 使用默认代码池）
    start_date=None,          # 开始日期，str "YYYY-MM-DD" 或 date 对象
    end_date=None,            # 结束日期
    trade_date=None,          # 单日查询（与 start/end 互斥）
    cycle="日线",
    fields=None,              # 返回字段列表（None = 全部）
    refresh=False,
    cache=True,
    code_kind=None,
    code_batch_size=None,
    max_workers=None,        # 批次并行 worker 数；None/1 = 串行，>1 = 并行提交多个代码批次
    progress=None,           # 可选：None = 自动；交互式环境默认开，脚本环境默认关
    max_codes=None,
    all_history=False,
    dataset="market_panel",   # 缓存命名使用的数据集名
    timeout_ms=None,
    adjust=None,              # None = 保持默认；0/none 不复权；1/ratio 比例复权；2/complex 复杂复权
    adjust_date=None,         # 复权基准日；-1 上市/成立日；0 天软当前/最后口径；不传时默认取 end_date/trade_date
)
```

复权行情按天软 `pn_rate()` / `pn_rateday()` 机制实现。这里要区分两个概念：

- `adjust` 选择除权算法，即用哪一类复权因子。
- `adjust_date` 选择价格锚点，即把整段价格序列复权到哪一天的价格口径。

| `adjust` | 含义 | 天软参数 |
|----------|------|----------|
| `0` / `"none"` | 不复权 | `Pn_rate()=0` |
| `1` / `"ratio"` / `"比例复权"` | 比例复权，采用交易所数据除权；天软文档说明该算法只考虑比例关系 | `Pn_rate()=1` |
| `2` / `"complex"` / `"复杂复权"` | 复杂复权，采用分红送配数据除权；除送股比例外，也考虑现金分红等加减关系 | `Pn_rate()=2` |

`adjust_date` 会写入 `Pn_rateday()`。它不是另一个复权算法，而是复权基准日：

| `adjust_date` 选择 | 常见名称 | 价格口径 |
|-------------------|----------|----------|
| `0`，或查询区间最后一个交易日/最新交易日 | 前复权 | 锚点日价格保持为真实行情口径，向前调整历史价格。天软 `Pn_rateday()=0` 表示当前/最后口径；tinydata 传 `adjust` 但不传 `adjust_date` 时默认使用本次查询结束日。 |
| `-1`，或上市日/成立日/首个有行情的有效交易日 | 后复权 | 起始日价格保持为真实行情口径，向后累积调整后续价格。天软 `Pn_rateday()=-1` 表示上市日/成立日口径。 |
| 查询区间中间任意交易日 | 定点复权 | 整段价格统一到该锚点日的价格口径。 |

因此，`adjust=1/2` 决定“比例复权还是复杂复权”，`adjust_date` 决定“前复权、后复权还是定点复权”。这里还要区分两种 `adjust_date` 用法：`-1` 是天软内置的“上市日/成立日口径”特殊值，明确对应常说的后复权；而具体日期值无论早晚，语义上都属于“复权到该日价格口径”的定点复权。若把具体日期设得非常早，并且它恰好等同于首个有效价格锚点，结果可能与后复权接近，但文档语义上仍应理解为定点复权，而不是 `-1` 这种专门的后复权口径。

全市场历史行情若需要加速，可组合使用较小的 `code_batch_size`（如 50~150）和 `max_workers>1` 并行抓取多个代码批次。注意这会提高并发请求数，若 OPI 租户较容易触发 429，应同步降低 `max_workers` 或增大 `request_interval`。若并行批次仍触发 429，tinydata 会自动降低 `max_workers` 并重试失败批次。`progress=None` 时，交互式环境默认开启进度条，脚本环境默认关闭；显式传 `progress=True/False` 可覆盖默认行为。终端里会显示 tqdm 风格进度条，IPython/Jupyter 会优先显示 notebook 友好的进度条；如果环境缺少 tqdm，则回退到原来的 stderr 文本进度条。直接命中本地缓存时通常不会显示进度条。

### realtime_bar / realtime_snapshot — 实时/近实时行情

```python
bars = td.realtime_bar(
    codes=["000001.SZ", "600000.SH"],
    window_minutes=5,       # 最近 5 分钟
    cycle="1分钟线",          # 默认 1 分钟线
    fields=["trade_time", "ts_code", "close", "volume"],
)

snap = td.realtime_snapshot(
    codes=["000001.SZ", "600000.SH"],
    window_minutes=240,     # 默认 240 分钟，便于午间/收盘附近取最近一行
    fields=["trade_time", "ts_code", "close", "volume"],
)
```

这两个接口复用 `markettable` 最近窗口查询，默认不使用本地缓存，适合盘中看最近成交 bar 或最新快照。它们必须显式传入 `codes`，不会因为 `codes=None` 自动请求全市场代码池。

#### realtime_bar

```python
td.realtime_bar(
    codes,
    *,
    window_minutes=5,
    end_time=None,
    cycle="1分钟线",
    fields=None,
    code_kind="stock",
    code_batch_size=200,
    max_workers=None,
    progress=None,
    max_codes=None,
    timeout_ms=None,
)
```

`realtime_bar()` 以 `end_time` 为窗口结束时间，向前回看 `window_minutes` 分钟，返回窗口内全部 bar。`end_time=None` 时使用当前本机时间；如果要做盘后复核或测试，可显式传入 `"YYYY-MM-DD HH:MM:SS"`。

#### realtime_snapshot

```python
td.realtime_snapshot(
    codes,
    *,
    window_minutes=240,
    end_time=None,
    cycle="1分钟线",
    fields=None,
    code_kind="stock",
    code_batch_size=200,
    max_workers=None,
    progress=None,
    max_codes=None,
    timeout_ms=None,
)
```

`realtime_snapshot()` 先调用 `realtime_bar()`，再按每个 `tsl_code` 保留 `trade_time` 最新的一行。默认 `window_minutes=240` 是为了在午间、收盘附近或盘后短时间内更容易取到最近一条；如果盘后较久调用仍为空，可继续增大窗口。

| 参数 | 说明 |
|------|------|
| `codes` | 必填，代码列表，支持 `000001.SZ` / `SZ000001` 等常用格式。 |
| `window_minutes` | 回看窗口分钟数，必须大于 0。 |
| `end_time` | 窗口结束时间；不传则使用当前本机时间。 |
| `cycle` | markettable 周期，默认 `1分钟线`；也可传天软支持的周期。 |
| `fields` | 返回字段；支持 `trade_time`、`ts_code`、`close`、`volume` 等别名。 |
| `code_kind` | 代码类型，默认 `stock`；查询基金行情、指数、期货等可按现有 market API 传对应类型。 |
| `code_batch_size` | 每批提交的代码数。 |
| `max_workers` | 并行请求批次数；触发 429 时会沿用行情层的降并发重试逻辑。 |
| `progress` | 是否显示进度条；`None` 时沿用自动判断。 |
| `max_codes` | 调试用，最多处理前 N 个代码。 |
| `timeout_ms` | 单次 OPI 请求超时毫秒数。 |

返回列与市场行情公共字段一致，通常包含 `trade_date`、`trade_time`、`tsl_code`、`ts_code`、`request_code`、行情字段、`cycle`、`dataset` 等。`realtime_bar()` 可能返回每个代码多行；`realtime_snapshot()` 每个代码最多返回一行。

### 所有市场数据集输出字段（公共）

所有 9 个市场数据集的输出列完全一致：

| 列名 | 类型 | 说明 |
|------|------|------|
| `trade_date` | date | 交易日期 |
| `tsl_code` | str | 天软原生代码（如 `SZ000001`） |
| `ts_code` | str | 标准代码（如 `000001.SZ`） |
| `request_code` | str | 请求时使用的代码 |
| `open` | float | 开盘价 |
| `high` | float | 最高价 |
| `low` | float | 最低价 |
| `close` | float | 收盘价 |
| `volume` | float | 成交量 |
| `amount` | float | 成交额 |
| `trade_time` | datetime | 数据获取时间戳 |
| `cycle` | str | 周期标识（daily/weekly/monthly） |
| `dataset` | str | 数据集名称 |
| `source_table_id` | int | 天软数据表 ID |
| `source_table_name` | str | 天软数据表名 |

### stock_daily — 股票日行情

```python
df = td.stock_daily(
    codes=None,          # 默认使用当前活跃 A 股股票池；如需含退市股票，请显式传 td.stock_codes(include_inactive=True)
    start_date="2024-01-01",
    end_date="2024-03-31",
    trade_date=None,
    fields=["trade_date", "ts_code", "close", "volume"],
    refresh=False,
    cache=True,
    adjust="complex",    # 可选：复杂复权
    adjust_date=None,    # 可选：默认 end_date
    max_workers=None,    # 可选：并行抓取多个代码批次；适合全市场历史行情
    progress=None,       # 可选：None = 自动；交互式环境默认开，脚本环境默认关
)
```

**示例：计算 20 日收益率**

```python
import pandas as pd
import tinydata as td

codes = td.stock_codes(include_inactive=False)  # 只取当前活跃 A 股，避免历史退市股票和全表权限差异
df = td.stock_daily(codes=codes, start_date="2023-01-01", end_date="2024-01-01")

pivot = df.pivot(index="trade_date", columns="ts_code", values="close")
ret20 = pivot.pct_change(20).iloc[-1].sort_values(ascending=False)
print(ret20.head(10))
```

### stock_weekly — 股票周行情

```python
df = td.stock_weekly(
    codes=None, start_date=None, end_date=None, trade_date=None,
    fields=None, refresh=False, cache=True,
)
```

### stock_monthly — 股票月行情

```python
df = td.stock_monthly(
    codes=None, start_date=None, end_date=None, trade_date=None,
    fields=None, refresh=False, cache=True,
)
```

### fund_daily — 基金日行情

```python
df = td.fund_daily(
    codes=None,   # 默认使用 fund_market_codes()
    start_date="2024-01-01",
    end_date="2024-06-30",
)
```

### index_daily — 指数日行情

```python
df = td.index_daily(
    codes=["SH000001", "SZ399001", "SZ399006"],
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

### cbond_daily — 可转债日行情

```python
df = td.cbond_daily(
    codes=None,   # 默认使用 bond_codes()
    start_date="2024-01-01",
    end_date="2024-03-31",
)
```

### future_daily — 期货日行情

```python
df = td.future_daily(
    codes=["IF2403", "IC2403"],
    start_date="2024-01-01",
    end_date="2024-03-31",
)
```

### option_daily — 期权日行情

```python
df = td.option_daily(
    codes=td.option_codes(trade_date="2024-01-02"),
    trade_date="2024-01-02",
)
```

### hk_daily — 港股日行情

```python
# hk_daily 无默认代码池（code_kind=None），必须显式传入代码
df = td.hk_daily(
    codes=["HKHS00700", "HKHS09988"],  # 港股天软格式代码
    start_date="2024-01-01",
    end_date="2024-03-31",
)
```

> **注意**：`hk_daily` 没有内置代码池，调用时必须显式传入 `codes`。

---

## 4 股票数据

### 安全查询说明

绝大多数股票数据集设置了 `safe_query_required=True`，即必须传入以下至少一个参数，否则抛出 `TinyDataParameterError`：

- `trade_date`
- `report_period`
- `start_date` + `end_date`（或只传其中一个）
- `all_history=True`（拉取全量历史，谨慎使用）

唯一例外：`stock_basic_ext` 无需日期参数。

### stock_basic_ext — 股票基本信息

```python
df = td.stock_basic_ext(
    codes=None,        # None = 全量 A 股
    fields=None,
    refresh=False,
    cache=True,
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` | str | 天软代码 |
| `ts_code` | str | 标准代码（自动计算） |
| `stock_name` | str | 股票简称 |
| `full_name` | str | 股票全称 |
| `isin_code` | str | ISIN 代码 |
| `exchange` | str | 交易所 |
| `industry` | str | 所属行业 |
| `list_date` | date | 上市日期 |
| `delist_date` | date | 退市日期 |
| `list_status` | str | 上市状态 |
| `is_hs` | str | 沪深港通标志 |
| `total_share` | float | 总股本 |
| `float_share` | float | 流通股本 |
| `free_share` | float | 自由流通股本 |
| `total_mv` | float | 总市值 |
| `circ_mv` | float | 流通市值 |

**示例**

```python
df = td.stock_basic_ext()
listed = df[df["list_status"].str.contains("上市|正常")]
print(f"当前上市股票: {len(listed)}")
```

### stock_suspend — 停复牌信息

```python
df = td.stock_suspend(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
    # 或 trade_date="2024-06-01"
)
```

**输出字段**（postprocess="stock_suspend" 额外生成）

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` | str | 天软代码 |
| `ts_code` | str | 标准代码 |
| `trade_date` | date | 日期 |
| `event_type` | str | 事件类型（停牌/复牌） |
| `event_text` | str | 事件说明 |

### stock_industry_versioned — 行业分类（历史版本）

```python
df = td.stock_industry_versioned(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
    all_history=True,
)
```

**输出字段**（postprocess="stock_industry" 额外生成）

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` | str | 天软代码 |
| `ts_code` | str | 标准代码 |
| `trade_date` | date | 分类生效日期 |
| `industry_source` | str | 分类体系（如申万/证监会） |
| `industry_l1` | str | 一级行业 |
| `industry_l2` | str | 二级行业 |
| `industry_l3` | str | 三级行业 |
| `industry_code` | str | 行业代码 |
| `source_name` | str | 分类体系全称 |

**示例：获取最新申万行业分类**

```python
df = td.stock_industry_versioned(all_history=True)
latest = (
    df[df["industry_source"].str.contains("申万")]
    .sort_values("trade_date")
    .groupby("tsl_code")
    .last()
    .reset_index()
)
print(latest[["ts_code", "industry_l1", "industry_l2"]].head())
```

### stock_fina_pit_ext — 财务指标点对点（PIT）

```python
df = td.stock_fina_pit_ext(
    codes=["SZ000001", "SH600000"],
    start_date="2020-01-01",
    end_date="2024-12-31",
)
```

**输出字段**（postprocess="stock_fina_pit" 额外生成，长表格式）

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` | str | 天软代码 |
| `ts_code` | str | 标准代码 |
| `trade_date` | date | 查询基准日 |
| `report_date` | date | 报告期 |
| `ann_date` | date | 公告日 |
| `finance_source` | str | 财务数据来源 |
| `metric_name` | str | 指标名称（中文） |
| `metric_expr` | str | 指标 TSL 表达式 |
| `metric_field_id` | str | 指标字段 ID |
| `metric_value` | float | 指标数值 |
| `metric_text` | str | 指标文字说明 |

> PIT 数据按公告日还原财务信息，是回测中避免未来数据的关键数据源。

### fina_indicator — 财务指标

```python
df = td.fina_indicator(
    codes=["SZ000001"],
    start_date="2020-01-01",
    end_date="2024-06-30",
)
```

**输出字段（核心字段）**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` | str | 天软代码 |
| `ts_code` | str | 标准代码 |
| `report_date` | date | 报告期 |
| `ann_date` | date | 公告日 |
| `eps` | float | 每股收益 |
| `bps` | float | 每股净资产 |
| `roe` | float | 净资产收益率 |
| `roa` | float | 总资产报酬率 |
| `gross_profit_margin_pct` | float | 销售毛利率(%) |
| `net_profit_margin_pct` | float | 净利率(%) |
| `debt_to_assets_pct` | float | 资产负债率(%) |
| `current_ratio` | float | 流动比率 |
| `quick_ratio` | float | 速动比率 |
| `total_revenue` | float | 营业总收入 |
| `net_profit` | float | 净利润 |
| `total_assets` | float | 总资产 |

### fina_balancesheet — 资产负债表

```python
df = td.fina_balancesheet(
    codes=["SZ000001"],
    report_period="2023-12-31",
)
```

**输出字段（主要项目）**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `report_date` | date | 报告期 |
| `ann_date` | date | 公告日 |
| `total_assets` | float | 资产总计 |
| `total_liab` | float | 负债合计 |
| `total_equity` | float | 所有者权益合计 |
| `money_cap` | float | 货币资金 |
| `accounts_receiv` | float | 应收账款 |
| `inventories` | float | 存货 |
| `fix_assets` | float | 固定资产净值 |
| `st_borr` | float | 短期借款 |
| `lt_borr` | float | 长期借款 |

### fina_income — 利润表

```python
df = td.fina_income(
    codes=["SZ000001"],
    start_date="2020-01-01",
    end_date="2024-06-30",
)
```

**输出字段（主要项目）**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `report_date` | date | 报告期 |
| `ann_date` | date | 公告日 |
| `total_revenue` | float | 营业总收入 |
| `revenue` | float | 营业收入 |
| `total_cogs` | float | 营业总成本 |
| `operate_profit` | float | 营业利润 |
| `total_profit` | float | 利润总额 |
| `income_tax` | float | 所得税费用 |
| `n_income` | float | 净利润 |
| `n_income_attr_p` | float | 归属母公司净利润 |

### fina_cashflow — 现金流量表

```python
df = td.fina_cashflow(
    codes=["SZ000001"],
    start_date="2023-01-01",
    end_date="2023-12-31",
)
```

**输出字段（主要项目）**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `report_date` | date | 报告期 |
| `ann_date` | date | 公告日 |
| `net_profit` | float | 净利润 |
| `n_cashflow_act` | float | 经营活动现金流净额 |
| `n_cashflow_inv_act` | float | 投资活动现金流净额 |
| `n_cash_flows_fnc_act` | float | 筹资活动现金流净额 |
| `c_cash_equ_end_period` | float | 期末现金及现金等价物余额 |

### fina_forecast — 业绩预告

```python
df = td.fina_forecast(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `report_date` | date | 预告报告期 |
| `ann_date` | date | 公告日 |
| `forecast_type` | str | 预告类型 |
| `net_profit_min` | float | 预计净利润下限 |
| `net_profit_max` | float | 预计净利润上限 |
| `last_net_profit` | float | 上期净利润 |
| `growth_rate_min_pct` | float | 增长率下限(%) |
| `growth_rate_max_pct` | float | 增长率上限(%) |
| `forecast_summary` | str | 预告摘要 |

### fina_express — 业绩快报

```python
df = td.fina_express(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `report_date` | date | 报告期 |
| `ann_date` | date | 公告日 |
| `revenue` | float | 营业收入 |
| `operate_profit` | float | 营业利润 |
| `total_profit` | float | 利润总额 |
| `n_income` | float | 净利润 |
| `total_assets` | float | 总资产 |
| `total_hldr_eqy_exc_min_int` | float | 净资产（不含少数股东权益） |
| `diluted_eps` | float | 摊薄每股收益 |
| `diluted_roe_pct` | float | 净资产收益率(%) |

### fina_mainbz — 主营业务构成（合并）

```python
# 三张子表分别对应行业/产品/地区分类
df_ind  = td.fina_mainbz_industry(codes=["SZ000001"], all_history=True)
df_prd  = td.fina_mainbz_product(codes=["SZ000001"], all_history=True)
df_area = td.fina_mainbz_area(codes=["SZ000001"], all_history=True)

# 或合并查询（增加 segment_type 列区分）
df = td.fina_mainbz(codes=["SZ000001"], all_history=True)
print(df["segment_type"].unique())  # ["industry", "product", "area"]
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `report_date` | date | 报告期 |
| `ann_date` | date | 公告日 |
| `bz_item` | str | 业务项目名称 |
| `bz_sales` | float | 主营业务收入 |
| `bz_profit` | float | 主营业务利润 |
| `bz_cost` | float | 主营业务成本 |
| `curr_type` | str | 货币类型 |
| `segment_type` | str | 分类类型（`fina_mainbz` 合并时添加） |

### fina_disclosure — 财报披露时间表

```python
df = td.fina_disclosure(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `report_date` | date | 报告期 |
| `pre_date` | date | 预约披露日期 |
| `actual_date` | date | 实际披露日期 |
| `modify_date` | date | 变更日期 |

### stock_public_trade_info — 龙虎榜

```python
df = td.stock_public_trade_info(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `trade_date` | date | 交易日期 |
| `reason` | str | 上榜原因 |
| `net_amount` | float | 净买入金额 |
| `buy_amount` | float | 买入金额 |
| `sell_amount` | float | 卖出金额 |
| `trader_name` | str | 营业部名称 |
| `trader_type` | str | 营业部类型 |

### stock_unlock_schedule — 解禁计划

```python
df = td.stock_unlock_schedule(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `ann_date` | date | 公告日 |
| `unlock_date` | date | 解禁日 |
| `float_share` | float | 解禁股份数量 |
| `float_ratio_pct` | float | 解禁占流通比例(%) |
| `lock_type` | str | 锁定类型 |
| `holder_name` | str | 股东名称 |

### stock_holder_change_ext — 股东变动

```python
df = td.stock_holder_change_ext(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `ann_date` | date | 公告日 |
| `holder_name` | str | 股东名称 |
| `holder_type` | str | 股东类型 |
| `change_type` | str | 变动类型 |
| `change_vol` | float | 变动股数 |
| `change_ratio_pct` | float | 变动比例(%) |
| `after_share` | float | 变动后持股数 |
| `after_ratio_pct` | float | 变动后持股比例(%) |

### stock_repurchase_ext — 股票回购

```python
df = td.stock_repurchase_ext(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `ann_date` | date | 公告日 |
| `end_date` | date | 回购截止日 |
| `proc` | str | 回购进度 |
| `exp_amount` | float | 预计回购金额 |
| `act_amount` | float | 已回购金额 |
| `exp_vol` | float | 预计回购数量 |
| `act_vol` | float | 已回购数量 |
| `high_limit` | float | 回购价格上限 |
| `low_limit` | float | 回购价格下限 |

### stock_namechange — 股票曾用名

```python
df = td.stock_namechange(codes=None, all_history=True)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `name` | str | 股票名称 |
| `start_date` | date | 名称生效日 |
| `end_date` | date | 名称结束日 |
| `change_reason` | str | 更名原因 |
| `ann_date` | date | 公告日 |

### stock_sharefloat — 流通股变动

```python
df = td.stock_sharefloat(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `ann_date` | date | 公告日 |
| `float_date` | date | 流通日期 |
| `float_share` | float | 流通股数 |
| `float_ratio_pct` | float | 流通占总股本比例(%) |
| `reason` | str | 变动原因 |

### stock_dividend — 分红送配

```python
df = td.stock_dividend(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `end_date` | date | 分红报告期 |
| `ann_date` | date | 预案公告日 |
| `record_date` | date | 股权登记日 |
| `ex_date` | date | 除权除息日 |
| `pay_date` | date | 派息日 |
| `cash_div` | float | 每股派息（元，含税） |
| `cash_div_tax` | float | 每股派息（元，税后） |
| `stk_div` | float | 每股送转（股） |
| `stk_bo_rate` | float | 每股送股比率 |
| `stk_co_rate` | float | 每股转增比率 |

### stock_holdernumber — 股东户数

```python
df = td.stock_holdernumber(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `ann_date` | date | 公告日 |
| `end_date` | date | 截止日期 |
| `holder_num` | int | 股东户数 |
| `holder_num_ratio_pct` | float | 较上期变化比例(%) |
| `avg_hold` | float | 人均持股数量 |
| `avg_hold_ratio_pct` | float | 人均持股比例(%) |

### 新增股票基础与股东类接口

这些接口来自《远端股票数据、模型、FAQ汇总》中的基础数据表和 FAQ 对照，均按天软 InfoTable 表实现。

```python
td.stock_ipo(codes=["000001.SZ"])                                      # 发行上市，表 12
td.stock_delist_solution(codes=["600087.SH"], all_history=True)         # 终止上市股份处理方案，表 17
td.stock_classification_info(codes=["SWHY"], all_history=True)          # 行业/分类属性信息，表 138
td.stock_top10_holder(codes=["000001.SZ"], report_period="20231231")    # 十大股东，表 24
td.stock_top10_float_holder(codes=["000001.SZ"], report_period="20231231")
td.stock_controller(codes=["000001.SZ"], report_period="20231231")      # 控股股东及实际控制人，表 29
td.stock_officer_hold_change(codes=["000001.SZ"], start_date="20200101", end_date="20241231")
td.stock_foreign_holding(codes=["603605.SH"], start_date="20240101", end_date="20241231")
td.stock_nonrecurring(codes=["000001.SZ"], report_period="20231231")    # 非经常性损益，表 150
td.stock_trade_time(codes=["000001.SH"], all_history=True)              # 证券交易时间，表 137
```

`stock_trade_time` 的 `codes` 使用证券品种代表代码，例如 `SH000001`、`SZ399106`。该表不是普通个股时间表，通常配合 `all_history=True` 后自行取指定日之前最近一条生效记录。

### stock_blocktrade — 大宗交易

```python
df = td.stock_blocktrade(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `trade_date` | date | 交易日期 |
| `price` | float | 成交价格 |
| `vol` | float | 成交量（万股） |
| `amount` | float | 成交金额（万元） |
| `buyer` | str | 买方营业部 |
| `seller` | str | 卖方营业部 |
| `discount_pct` | float | 折溢价率(%) |

### stock_margin — 两融汇总（市场级）

```python
# stock_margin 使用市场级融资融券代码，非个股代码
df = td.stock_margin(
    start_date="2024-01-01",
    end_date="2024-12-31",
    # codes 默认为 ["RZRQ000001", "RZRQ000002", "RZRQ000003"]
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` | str | 市场代码（RZRQ000001/2/3） |
| `trade_date` | date | 截止日 |
| `rzye` | float | 融资余额（元） |
| `rzmre` | float | 融资买入额（元） |
| `rzche` | float | 融资偿还额（元） |
| `rqye` | float | 融券余额（元） |
| `rqmcl` | float | 融券卖出量（股） |
| `rqchl` | float | 融券偿还量（股） |
| `rqyl` | float | 融券余量（股） |
| `rzrqye` | float | 融资融券余额（元） |

> `stock_margin` 使用 `code_kind="margin_market"`，对应市场汇总代码。如需个股两融明细，请用 `stock_margindetail`。
> 公开 API 没有单独导出 `td.margin_market_codes()`；`stock_margin()` 内部默认使用 `RZRQ000001`、`RZRQ000002`、`RZRQ000003` 这 3 个市场级代码。

### stock_margindetail — 两融明细（个股）

```python
df = td.stock_margindetail(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `trade_date` | date | 截止日 |
| `margin_buy_amount` | float | 融资买入额 |
| `margin_repay_amount` | float | 融资偿还额 |
| `margin_balance` | float | 融资余额 |
| `short_sell_volume` | float | 融券卖出量 |
| `short_repay_volume` | float | 融券偿还量 |
| `short_balance_volume` | float | 融券余量 |
| `short_balance_amount` | float | 融券余额 |
| `margin_short_balance` | float | 融资融券余额 |

### stock_margin_collateral — 融资融券担保券

```python
df = td.stock_margin_collateral(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `trade_date` | date | 截止日 |
| `prev_collateral_volume` | float | 上一交易日担保证券数量 |
| `collateral_volume_change` | float | 当日担保证券数量变动 |
| `collateral_volume` | float | 当日担保证券数量 |
| `collateral_market_value` | float | 担保证券市值 |
| `total_market_value` | float | 证券总市值 |
| `collateral_market_value_ratio_pct` | float | 担保证券市值占总市值比重(%) |

### stock_hsgt_daily — 沪深港通每日成交汇总

```python
# code_kind="hsgt_channel"，按通道查询（共4个通道）
df = td.stock_hsgt_daily(
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `trade_date` | date | 日期 |
| `channel_code` | str | 通道代码（HG000001~HG000004） |
| `channel_name` | str | 通道名称（沪股通/深股通等） |
| `amount_total_rmb` | float | 买卖总成交额（人民币） |
| `buy_amount_rmb` | float | 买入成交额（人民币） |
| `sell_amount_rmb` | float | 卖出成交额（人民币） |
| `amount_total_hkd` | float | 买卖总成交额（港币） |
| `buy_amount_hkd` | float | 买入成交额（港币） |
| `sell_amount_hkd` | float | 卖出成交额（港币） |
| `trade_count_total` | float | 买卖总成交数目 |
| `buy_count` | float | 买入成交数目 |
| `sell_count` | float | 卖出成交数目 |
| `quota_balance` | float | 每日额度余额 |
| `stock_etf_amount` | float | 股票+ETF买卖成交额 |
| `etf_amount` | float | ETF买卖成交额 |

### stock_hsgt_top10 — 沪深港通十大成交活跃股

```python
df = td.stock_hsgt_top10(
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `trade_date` | date | 日期 |
| `channel_code` | str | 通道代码 |
| `channel_name` | str | 通道名称 |
| `security_code_raw` | str | 证券代码（原始） |
| `security_name` | str | 证券名称 |
| `buy_amount` | float | 买入金额 |
| `sell_amount` | float | 卖出金额 |
| `amount_total` | float | 买卖总金额 |
| `rank_no` | int | 排名 |

### stock_hsgt_hold — 沪深港通持股明细

```python
df = td.stock_hsgt_hold(
    codes=None,   # code_kind="hsgt_stock"
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `trade_date` | date | 日期 |
| `channel_code` | str | 通道代码 |
| `channel_name` | str | 通道名称 |
| `security_code_raw` | str | 证券代码（原始） |
| `security_name` | str | 证券名称 |
| `holding_volume` | float | 持股数量 |
| `total_share_ratio_pct` | float | 占总股本比例(%) |

### stock_hsgt_short_balance — 沪深股通卖空数据

```python
df = td.stock_hsgt_short_balance(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `trade_date` | date | 日期 |
| `channel_code` | str | 通道代码 |
| `channel_name` | str | 通道名称 |
| `security_code_raw` | str | 证券代码（原始） |
| `security_name` | str | 证券名称 |
| `short_balance_volume` | float | 可供/实际卖空股数余额 |

### stock_lending_summary — 转融通证券出借汇总

```python
df = td.stock_lending_summary(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `trade_date` | date | 截止日 |
| `tenor_days` | int | 期限（天） |
| `rate_pct` | float | 费率(%) |
| `declare_type` | str | 申报类型 |
| `deal_volume` | float | 成交量 |
| `data_type` | str | 数据类型 |

### stock_lending_trade — 转融券交易明细

```python
df = td.stock_lending_trade(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `trade_date` | date | 截止日 |
| `tenor_days` | int | 期限（天） |
| `rate_pct` | float | 费率(%) |
| `lend_volume` | float | 融出数量 |

### stock_lending_balance — 转融券余量

```python
df = td.stock_lending_balance(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `trade_date` | date | 截止日 |
| `balance_volume` | float | 余量 |
| `balance_amount` | float | 余额 |

### stock_pledge_summary — 股票质押回购汇总

```python
# code_kind="market"，按市场代码汇总
df = td.stock_pledge_summary(
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `market_code` | str | 市场代码 |
| `trade_date` | date | 截止日 |
| `initial_trade_amount` | float | 初始交易金额 |
| `repurchase_trade_amount` | float | 购回交易金额 |

### stock_pledge_detail — 股票质押回购明细

```python
df = td.stock_pledge_detail(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `security_code_raw` | str | 证券代码（原始） |
| `trade_date` | date | 截止日 |
| `initial_trade_volume` | float | 初始交易数量 |
| `repurchase_trade_volume` | float | 购回交易数量 |

### stock_pledge_balance — 股票质押回购余量

```python
df = td.stock_pledge_balance(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 股票代码 |
| `security_code_raw` | str | 证券代码（原始） |
| `trade_date` | date | 截止日 |
| `balance_volume` | float | 余量 |
| `unrestricted_balance_volume` | float | 无限售股份余量 |
| `restricted_balance_volume` | float | 有限售股份余量 |
| `data_source` | str | 数据来源 |

### stock_pledge_rate — 股票质押平均质押率

```python
# code_kind="market"，按市场代码汇总
df = td.stock_pledge_rate(
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `market_code` | str | 市场代码 |
| `trade_date` | date | 截止日 |
| `unrestricted_pledge_rate_pct` | float | 无限售条件股份质押率(%) |
| `restricted_pledge_rate_pct` | float | 有限售条件股份质押率(%) |

---

## 5 基金数据

大多数基金数据集 `safe_query_required=False`（无需日期参数可全量查询），但以下函数**需要**日期参数：

`fund_nav`、`fund_adjusted_nav`、`fund_share`、`fund_nav_benchmark_return`、`fund_balance_sheet`、`fund_income_statement`、`fund_buy_sell`、`fund_dividend`、`fund_split`、`fund_etf_sub_redemption`、`fund_financial_quarterly_ext`、`fund_fof_holding_detail`、`fund_stock_holding_detail`、`fund_industry_alloc`、`fund_asset_alloc`、`fund_bond_alloc`、`fund_bond_holding_detail`、`fund_abs_holding_detail`、`fund_cbond_holding_detail`、`fund_top_holder`、`fund_holder_structure`、`fund_broker_seat`

天软基金定期报告类表的取数代码不总是用户看到的份额代码：A/B/C 等不同收费份额多数要用“不同收费模式基金主代码”，分级基金要用“母基金代码”。tinydata 对已确认的定报表自动做这类映射，返回的 `tsl_code` 是实际用于取数的主代码/母基金代码。

### fund_basic_ext — 基金基本信息

> **别名**：`fund_basic = fund_basic_ext`

```python
df = td.fund_basic_ext(codes=None, fields=None, refresh=False, cache=True)
# 等价于
df = td.fund_basic(codes=None)
```

**核心输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 基金代码 |
| `fund_name` | str | 基金名称 |
| `fund_short_name` | str | 基金简称 |
| `fund_type` | str | 基金类型 |
| `trade_mode` | str | 交易方式 |
| `invest_style` | str | 投资风格 |
| `invest_type` | str | 投资类型 |
| `active_passive` | str | 主动/被动 |
| `share_class` | str | 份额类别 |
| `found_date` | date | 设立日 |
| `list_date` | date | 上市日期 |
| `liquidation_date` | date | 清算日 |
| `management` | str | 基金管理人 |
| `custodian` | str | 基金托管人 |
| `benchmark` | str | 业绩比较基准 |
| `tracking_index_code_raw` | str | 标的指数代码（原始） |
| `list_location` | str | 上市地 |
| `trade_code` | str | 交易代码 |
| `investment_objective` | str | 投资目标 |
| `investment_scope` | str | 投资范围 |
| `investment_strategy` | str | 投资策略 |
| `risk_return_feature` | str | 风险收益特征 |
| `raise_total_amount` | float | 募集总金额 |
| `raise_total_share` | float | 募集总份额 |

### fund_manager_ext — 基金经理信息

> **别名**：`fund_manager = fund_manager_ext`

```python
df = td.fund_manager_ext(codes=None, fields=None, refresh=False, cache=True)
# 等价于
df = td.fund_manager(codes=None)
```

**核心输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 基金代码 |
| `fund_name` | str | 基金名称 |
| `ann_date` | date | 公布日 |
| `info_source` | str | 信息来源 |
| `manager_name` | str | 基金经理姓名 |
| `begin_date` | date | 任职日 |
| `end_date` | date | 任职结束日期 |
| `manager_code` | str | 基金经理代码 |
| `is_current` | str | 在任与否 |
| `age` | int | 年龄 |
| `position` | str | 职务 |
| `education` | str | 学历 |

**示例：统计在任基金经理管理基金数**

```python
df = td.fund_manager_ext()
active = df[df["is_current"].astype(str).isin(["1", "是", "Y", "True", "true"])]
mgr_count = active.groupby("manager_name")["ts_code"].nunique().sort_values(ascending=False)
print(mgr_count.head(10))
```

### 新增基金基础、定报与 ETF PCF 接口

这些接口来自《远端基金数据、模型、FAQ汇总》中的基金数据表和 FAQ 对照。

```python
td.fund_benchmark(codes=["502049.SH"])                                  # 业绩比较基准，表 303
td.fund_fee(codes=["502004.SH"])                                        # 开放式基金费率，表 309
td.fund_nav_benchmark_return(codes=["000814.OF"], report_period="20231231")
td.fund_balance_sheet(codes=["004905.OF"], report_period="20231231")    # 资产负债表，表 312
td.fund_income_statement(codes=["160127.OF"], report_period="20231231") # 收益及分配，表 314
td.fund_buy_sell(codes=["004905.OF"], report_period="20231231")         # 累计买入和卖出，表 319
td.fund_dividend(codes=["000001.OF"], start_date="20200101", end_date="20241231")
td.fund_split(codes=["160127.OF"], all_history=True)
td.fund_namechange(codes=["000001.OF"])
td.fund_etf_sub_redemption(codes=["159901.OF"], start_date="20100701", end_date="20100803")
td.fund_etf_constituent(codes=["510050.OF"], trade_date="20190816")
```

`fund_etf_sub_redemption` 是 ETF 申购赎回基本信息表 346；`fund_etf_constituent` 封装天软 `GetFundETFConstituent`，用于取指定日 PCF 成分股。`fund_fee` 的 `公布日`、`生效日` 在天软样例和 FAQ 中可能为 0，tinydata 会转换为缺失日期，不把 0 当成真实日期。

`fund_etf_constituent`、`fund_adjusted_nav`、`index_member_snapshot`、`index_weight` 这类自定义 TSL 函数接口按代码逐个请求，不使用 `code_batch_size`，但现在支持 `max_workers` 和 `progress`。当 `max_workers>1` 时会并行处理多个代码；若触发 OPI 429，tinydata 会自动降低 `max_workers` 并重试失败代码。`progress=True` 时终端里会显示 tqdm 风格进度条，IPython/Jupyter 会优先显示 notebook 友好的进度条。

### fund_classification_info — 基金分类信息

```python
# code_kind=None, allow_full_table=True，始终返回全表，无需传 codes
df = td.fund_classification_info()
```

**核心输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `attr_code` | str | 属性代码 |
| `attr_name` | str | 属性名称 |
| `level_no` | int | 层级 |
| `parent_attr_code` | str | 上级属性代码 |
| `parent_attr_name` | str | 上级属性名称 |
| `in_date` | date | 入选日期 |
| `out_date` | date | 剔除日期 |
| `is_latest` | int | 最新标识 |
| `root_attr_code` | str | 所属属性代码 |

### fund_classification_member — 基金分类成员

```python
df = td.fund_classification_member(codes=None, fields=None, refresh=False, cache=True)
```

**核心输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 基金代码 |
| `attr_code` | str | 属性代码 |
| `attr_name` | str | 属性名称 |
| `level_no` | int | 层级 |
| `in_date` | date | 入选日期 |
| `out_date` | date | 剔除日期 |
| `is_latest` | int | 最新标识 |
| `root_attr_code` | str | 所属属性代码 |
| `root_attr_name` | str | 所属属性名称 |

### fund_nav — 基金净值

```python
df = td.fund_nav(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
    # 或 trade_date="2024-06-28"
)
```

**核心输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 基金代码 |
| `trade_date` | date | 净值日期 |
| `ann_date` | date | 公布日 |
| `nav_week` | int | 净值所在周 |
| `unit_nav` | float | 单位净值 |
| `accum_nav` | float | 累计净值 |
| `daily_profit_per_10k` | float | 每万份基金单位收益 |
| `seven_day_annualized_return_pct` | float | 最近七日收益折算的年收益率(%) |
| `update_time` | str | 更新时间 |
| `remark` | str | 备注 |

### fund_adjusted_nav — 基金复权净值

封装天软 `FundNAWByRateBegtEndt`，返回区间内的**复权净值**序列。
复权净值反映拆分/分红/分级折算等影响后的真实持有收益，是回测和净值曲线分析的核心字段。

```python
df = td.fund_adjusted_nav(
    codes=["510050.OF"],
    start_date="20190101",
    end_date="20190425",
    adjust=1,        # 1=后复权（默认）, 2=前复权
    adjust_date=-1,  # -1=以基金成立日为基准（后复权常用）；0=以最新净值日为基准（前复权常用）；或具体日期
    max_workers=4,   # 可选：并行处理多个基金代码
    progress=True,   # 可选：显示环境感知代码级进度条
)
```

**参数说明**

| 参数 | 说明 |
|------|------|
| `codes` | 必填，基金代码列表（支持父子代码自动归一） |
| `start_date` / `end_date` | 必填，区间起止日 |
| `adjust` | 1=后复权（back-adjust），2=前复权（forward-adjust）；传入 0/None 会报错并提示改用 `fund_nav` |
| `adjust_date` | -1（默认，成立日）/ 0（最新净值日）/ 具体日期作为复权基准日 |
| `max_workers` | 可选，代码级并行 worker 数；`None/1` = 串行，`>1` = 并行 |
| `progress` | 可选，`True` 时显示环境感知代码级进度条 |

**核心输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 基金代码 |
| `trade_date` | date | 净值日期 |
| `unit_nav` | float | 单位净值 |
| `accum_nav` | float | 累计净值 |
| `adjusted_nav` | float | 复权净值 |
| `adjust_factor` | float | 复权因子 |
| `adjusted_return_pct` | float | 复权净值增长率(%) |
| `split_ratio` | float | 份额拆分比 |
| `dividend_ratio` | float | 红利比 |
| `adjust` / `adjust_date` / `begin_date` / `end_date` | - | 请求参数回填，便于追溯 |

> FAQ 参考：天软 FAQ id=18021（基金复权净值及 pn_rate / PN_RateDay 语义）。

### fund_share — 基金份额

```python
df = td.fund_share(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

**核心输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 基金代码 |
| `change_date` | date | 变动日 |
| `info_source` | str | 信息来源 |
| `total_share` | float | 总份额 |
| `non_tradable_share` | float | 未流通份额 |
| `sponsor_share` | float | 发起人持有份额 |
| `tradable_share` | float | 流通份额 |
| `change_reason` | str | 变动原因 |
| `remark` | str | 备注 |

### fund_financial_quarterly_ext — 基金财务季报

```python
df = td.fund_financial_quarterly_ext(
    codes=None,
    start_date="2023-01-01",
    end_date="2024-06-30",
)
```

**核心输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 基金代码 |
| `fund_name` | str | 基金名称 |
| `report_date` | date | 报告期 |
| `ann_date` | date | 公告日 |
| `net_income` | float | 净收益 |
| `period_profit` | float | 本期利润 |
| `weighted_avg_share_profit` | float | 加权平均基金份额本期利润 |
| `unit_net_income` | float | 期末可供分配基金份额净收益 |
| `distributable_net_income` | float | 期末可供分配利润 |
| `unit_distributable_net_income` | float | 期末可供分配基金份额利润 |
| `net_asset` | float | 基金净资产（元） |
| `total_asset` | float | 基金总资产（元） |
| `unit_net_asset` | float | 基金份额净值 |
| `net_asset_return_pct` | float | 净资产收益率(%) |
| `net_asset_growth_pct` | float | 净资产增长率(%) |
| `cum_nav_growth_pct` | float | 累计净值增长率(%) |
| `remark` | str | 备注 |

### fund_fof_holding_detail — FOF 基金持仓明细

```python
df = td.fund_fof_holding_detail(
    codes=None,
    start_date="2023-01-01",
    end_date="2024-06-30",
)
```

**核心输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | FOF 基金代码 |
| `fund_name` | str | FOF 基金名称 |
| `report_date` | date | 报告期 |
| `holding_name` | str | 持有基金名称 |
| `holding_code_raw` | str | 持有基金代码（原始） |
| `quantity` | float | 持有数量 |
| `market_value` | float | 持有市值 |
| `nav_ratio_pct` | float | 占基金净值比例(%) |
| `rank_no` | int | 排名 |
| `is_related_fund` | str | 是否关联基金 |

### fund_stock_holding_detail — 基金股票持仓明细

> **别名**：`fund_stock_holding = fund_stock_holding_detail`

```python
df = td.fund_stock_holding_detail(
    codes=None,
    start_date="2023-01-01",
    end_date="2024-06-30",
)
```

**核心输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 基金代码 |
| `fund_name` | str | 基金名称 |
| `report_date` | date | 报告期 |
| `ann_date` | date | 公告日 |
| `security_code_raw` | str | 股票代码（原始） |
| `security_name` | str | 股票名称 |
| `quantity` | float | 持股数量 |
| `market_value` | float | 持股市值 |
| `nav_ratio_pct` | float | 占基金净值比例(%) |
| `rank_no` | int | 排名 |
| `index_invest_quantity` | float | 指数投资数量 |
| `index_invest_market_value` | float | 指数投资市值 |
| `active_invest_quantity` | float | 主动投资数量 |
| `active_invest_market_value` | float | 主动投资市值 |
| `board_name` | str | 板块名称 |
| `remark` | str | 备注 |

**示例：查询某报告期全市场重仓股**

```python
df = td.fund_stock_holding_detail(
    start_date="2024-06-30",
    end_date="2024-06-30",
)
top_holdings = (
    df.groupby("security_code_raw")["market_value"]
    .sum()
    .sort_values(ascending=False)
    .head(20)
)
print(top_holdings)
```

### fund_industry_alloc — 基金行业配置

```python
df = td.fund_industry_alloc(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-06-30",
)
```

**核心输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 基金代码 |
| `fund_name` | str | 基金名称 |
| `report_date` | date | 报告期 |
| `ann_date` | date | 公告日 |
| `industry_name` | str | 行业名称 |
| `market_value` | float | 行业市值（元） |
| `nav_ratio_pct` | float | 占净值比例(%) |
| `remark` | str | 备注 |

### fund_asset_alloc — 基金资产配置

```python
df = td.fund_asset_alloc(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-06-30",
)
```

**核心输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 基金代码 |
| `fund_name` | str | 基金名称 |
| `report_date` | date | 报告期 |
| `ann_date` | date | 公告日 |
| `equity_investment` | float | 权益投资 |
| `equity_nav_ratio_pct` | float | 权益投资占净值比例(%) |
| `stock_market_value` | float | 股票市值 |
| `stock_nav_ratio_pct` | float | 股票占净值比例(%) |
| `fund_market_value` | float | 基金市值 |
| `fund_nav_ratio_pct` | float | 基金占净值比例(%) |
| `bond_market_value` | float | 债券市值 |
| `bond_nav_ratio_pct` | float | 债券占净值比例(%) |
| `other_asset_value` | float | 其他资产价值 |
| `other_asset_nav_ratio_pct` | float | 其他资产占净值比例(%) |
| `net_asset_value` | float | 资产净值 |
| `total_asset_value` | float | 资产总值 |
| `remark` | str | 备注 |

### fund_bond_alloc — 基金债券配置

```python
df = td.fund_bond_alloc(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-06-30",
)
```

**核心输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 基金代码 |
| `fund_name` | str | 基金名称 |
| `report_date` | date | 报告期 |
| `ann_date` | date | 公告日 |
| `bond_category` | str | 债券类别/行业名称 |
| `market_value` | float | 持有市值 |
| `nav_ratio_pct` | float | 占净值比例(%) |
| `bond_market_ratio_pct` | float | 占债券市值比例(%) |
| `remark` | str | 备注 |

### fund_bond_holding_detail — 基金债券持仓明细

> **别名**：`fund_bond_holding = fund_bond_holding_detail`

```python
df = td.fund_bond_holding_detail(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-06-30",
)
```

**核心输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 基金代码 |
| `fund_name` | str | 基金名称 |
| `report_date` | date | 报告期 |
| `ann_date` | date | 公告日 |
| `bond_code_raw` | str | 债券代码（原始） |
| `bond_name` | str | 债券名称 |
| `quantity` | float | 持有数量 |
| `market_value` | float | 持有市值 |
| `nav_ratio_pct` | float | 占净值比例(%) |
| `rank_no` | int | 排名 |
| `bond_type` | str | 债券类型 |
| `is_convertible_period` | str | 是否处于转股期 |
| `remark` | str | 备注 |

### fund_abs_holding_detail — 基金 ABS 持仓明细

```python
df = td.fund_abs_holding_detail(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-06-30",
)
```

**核心输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 基金代码 |
| `report_date` | date | 报告期 |
| `asset_name` | str | ABS 名称 |
| `asset_code_raw` | str | ABS 代码（原始） |
| `quantity` | float | 持有数量 |
| `market_value` | float | 持有市值 |
| `nav_ratio_pct` | float | 占净值比例(%) |
| `rank_no` | int | 排名 |

### fund_cbond_holding_detail — 基金可转债持仓明细

```python
df = td.fund_cbond_holding_detail(
    codes=None,
    start_date="2024-01-01",
    end_date="2024-06-30",
)
```

**核心输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 基金代码 |
| `report_date` | date | 报告期 |
| `cbond_code_raw` | str | 可转债代码（原始） |
| `cbond_name` | str | 可转债名称 |
| `quantity` | float | 持有数量 |
| `market_value` | float | 持有市值 |
| `nav_ratio_pct` | float | 占净值比例(%) |
| `rank_no` | int | 排名 |

### fund_top_holder — 基金大额持有人

```python
df = td.fund_top_holder(
    codes=None,
    start_date="2023-06-30",
    end_date="2024-06-30",
)
```

**核心输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 基金代码 |
| `fund_name` | str | 基金名称 |
| `report_date` | date | 报告期 |
| `ann_date` | date | 公告日 |
| `holder_name` | str | 持有人名称 |
| `holder_type` | str | 持有人类型 |
| `holding_share` | float | 持有份额 |
| `total_share_ratio_pct` | float | 占总份额比例(%) |
| `remark` | str | 备注 |

### fund_holder_structure — 基金持有人结构

```python
df = td.fund_holder_structure(
    codes=None,
    start_date="2023-06-30",
    end_date="2024-06-30",
)
```

**核心输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 基金代码 |
| `fund_name` | str | 基金名称 |
| `report_date` | date | 报告期 |
| `holder_count` | int | 持有人户数 |
| `avg_share_per_holder` | float | 户均持有份额 |
| `institution_share` | float | 机构持有份额 |
| `institution_ratio_pct` | float | 机构持有比例(%) |
| `individual_share` | float | 个人持有份额 |
| `individual_ratio_pct` | float | 个人持有比例(%) |
| `staff_share` | float | 基金管理人从业人员持有份额 |
| `staff_ratio_pct` | float | 从业人员持有比例(%) |
| `remark` | str | 备注 |

### fund_broker_seat — 基金券商席位交易

```python
df = td.fund_broker_seat(
    codes=None,
    start_date="2023-01-01",
    end_date="2023-12-31",
)
```

**核心输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `tsl_code` / `ts_code` | str | 基金代码 |
| `fund_name` | str | 基金名称 |
| `report_date` | date | 报告期 |
| `ann_date` | date | 公告日 |
| `broker_name` | str | 券商名称 |
| `trading_unit_count` | int | 交易单元数量 |
| `stock_trade_amount` | float | 股票成交量 |
| `stock_trade_ratio_pct` | float | 占股票成交总量比例(%) |
| `commission` | float | 佣金（元） |
| `commission_ratio_pct` | float | 占佣金总量比例(%) |
| `bond_trade_amount` | float | 债券成交量 |
| `bond_trade_ratio_pct` | float | 占债券成交总量比例(%) |
| `repo_trade_amount` | float | 回购成交量 |
| `repo_trade_ratio_pct` | float | 占回购成交总量比例(%) |
| `fund_trade_amount` | float | 基金成交金额 |
| `fund_trade_ratio_pct` | float | 占基金成交总额比例(%) |
| `remark` | str | 备注 |

---

## 6 债券数据

### bond_basic_ext — 债券基本信息

```python
df = td.bond_basic_ext(codes=None, fields=None, refresh=False, cache=True)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `source_code` | str | 天软原始代码 |
| `bond_ts_code` | str | 债券标准代码（自动计算） |
| `underlying_ts_code` | str | 正股标准代码（自动计算） |
| `bond_code_raw` | str | 债券代码 |
| `bond_full_name` | str | 债券全称 |
| `bond_short_name` | str | 债券简称 |
| `bond_full_name_en` | str | 债券英文全称 |
| `issue_year` | int | 发行年度 |
| `issue_start_date` | date | 发行起始日 |
| `issue_end_date` | date | 发行截止日 |
| `issue_amount` | float | 发行额 |
| `issue_volume` | float | 发行数量 |
| `issue_price` | float | 发行价格 |
| `par_value` | float | 面额 |
| `certificate_type` | str | 凭证类别 |
| `rate_type` | str | 利率品种 |
| `bond_type` | str | 债券种类 |
| `interest_calc_method` | str | 计息方式 |
| `maturity_years` | float | 偿还年限 |
| `coupon_rate_pct` | float | 票面利率(%) |
| `base_rate_code` | str | 基准利率代码 |
| `base_spread_pct` | float | 基本利差(%) |
| `step_rate_pct` | float | 递进利率(%) |
| `interest_payment_method` | str | 付息方式 |
| `interest_payment_desc` | str | 付息说明 |
| `interest_payment_frequency` | float | 付息频率（次/年） |
| `interest_start_date` | date | 计息日 |
| `list_date` | date | 上市日期 |
| `maturity_date` | date | 到期日 |
| `actual_maturity_date` | date | 实际到期日 |
| `delist_date` | date | 摘牌日 |
| `stop_trade_date` | date | 停止交易日 |
| `redeem_start_date` | date | 兑付起始日 |
| `redeem_end_date` | date | 兑付截止日 |
| `convert_start_date` | date | 转股开始日 |
| `convert_end_date` | date | 停止转股日 |
| `list_location` | str | 上市地点 |
| `issue_target` | str | 发行对象 |
| `underlying_code_raw` | str | 正股代码（原始） |
| `sh_bond_code` | str | 上交所债券代码 |
| `sz_bond_code` | str | 深交所债券代码 |
| `interbank_bond_code` | str | 银行间债券代码 |
| `credit_rating` | str | 信用等级 |
| `external_guarantee_method` | str | 外部信用担保方式 |
| `eval_bond_category` | str | 债券类别（评价用） |
| `eval_bond_rating` | str | 债券评级（评价用） |
| `underlying_sw_industry_l1` | str | 正股申万一级行业 |
| `underlying_csrc_industry_l1` | str | 正股证监会一级行业 |
| `issuer_code` | str | 债券主体代码 |
| `issuer_name` | str | 债券主体名称 |
| `bond_industry` | str | 债券所属行业 |
| `is_option_embedded` | str | 是否含权债 |
| `is_early_redeemable` | str | 是否可提前兑付 |
| `issuer_nature` | str | 债券主体性质 |
| `remark` | str | 备注 |

---

## 7 指数与交易日历

### trade_calendar — 交易日历

```python
df = td.trade_calendar(
    start_date="2024-01-01",
    end_date="2024-12-31",
    codes=["SH000001"],   # 默认使用 market_codes()
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `trade_date` | date | 日期 |
| `market_code` | str | 市场代码 |
| `market_name` | str | 市场名称 |
| `is_trade_day` | bool | 是否交易日 |
| `trade_day_type` | str | 交易日类别 |
| `remark` | str | 备注 |

**示例：获取 2024 年所有交易日**

```python
df = td.trade_calendar(
    start_date="2024-01-01",
    end_date="2024-12-31",
    codes=["SH000001"],
)
trade_days = df[df["is_trade_day"] == True]["trade_date"].tolist()
print(f"2024年交易日数: {len(trade_days)}")
```

### market_calendar_multi — 多市场交易日历

```python
df = td.market_calendar_multi(
    codes=td.market_codes(),   # 返回全部市场的日历
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

输出字段与 `trade_calendar` 相同。

### index_basic_ext — 指数基本信息

```python
df = td.index_basic_ext(codes=None, fields=None, refresh=False, cache=True)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `index_code_raw` | str | 指数代码（原始） |
| `index_ts_code` | str | 指数标准代码（自动计算） |
| `latest_change_date` | date | 最新变更日 |
| `short_name` | str | 指数简称 |
| `full_name` | str | 指数全称 |
| `index_type` | str | 指数类型 |
| `index_target` | str | 指数标的 |
| `publisher` | str | 指数所属公司/发布机构 |
| `start_date` | date | 指数起始日期 |
| `found_date` | date | 指数成立日期 |
| `stop_date` | date | 停用日期 |
| `base_point` | float | 基准点数 |
| `weighting_method` | str | 加权方式 |
| `sample_count` | int | 样本个数 |
| `sample_adjust_frequency` | str | 样本调整周期 |
| `category_l1` | str | 指数一级分类 |
| `category_l2` | str | 指数二级分类 |
| `category_l3` | str | 指数三级分类 |
| `category_l4` | str | 指数四级分类 |
| `main_index_code_raw` | str | 指数主代码（原始） |
| `remark` | str | 备注 |

### index_member_versioned — 指数成份历史

```python
df = td.index_member_versioned(
    codes=["SH000300"],   # 沪深300
    all_history=True,
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `index_code_raw` | str | 指数代码（原始） |
| `index_ts_code` | str | 指数标准代码 |
| `con_code_raw` | str | 成份证券代码（原始） |
| `con_ts_code` | str | 成份证券标准代码 |
| `latest_change_date` | date | 最新变更日 |
| `in_date` | date | 入选日期 |
| `out_date` | date | 剔除日期 |
| `member_flag` | int | 成份标志（1=在成份内） |
| `in_ann_date` | date | 入选公布日 |
| `out_ann_date` | date | 剔除公布日 |
| `in_adjust_type` | str | 入选调整类型 |
| `out_adjust_type` | str | 剔除调整类型 |

**示例：查询沪深300当前成份股**

```python
df = td.index_member_versioned(codes=["SH000300"], all_history=True)
current = df[(df["member_flag"] == 1) & (df["out_date"].isna())]
print(f"当前沪深300成份股数: {len(current)}")
```

---

### index_member_snapshot — 指数指定日成份股快照

封装天软 `GetBKByDate(板块代码, 日期, ExType)`，按日返回该指数当日的成份股代码列表（不带权重）。
适合做某一日快照、回测当日成份范围，或与 `index_member_versioned` 结果做交叉校验。

```python
df = td.index_member_snapshot(
    codes=["000300.CSI"],
    trade_date="20210107",
    extend=False,   # True 时使用 ExType=1，包含暂停上市/退市等扩展成份
    max_workers=4,  # 可选：并行处理多个指数代码
    progress=True,  # 可选：显示环境感知代码级进度条
)
```

**参数说明**

| 参数 | 说明 |
|------|------|
| `codes` | 指数代码，支持 `000300.CSI` / `SH000300` 等格式 |
| `trade_date` | 必填，YYYYMMDD 或 `datetime` |
| `extend` | False（默认 ExType=0，仅当日有效成份）/ True（ExType=1，扩展） |
| `max_workers` | 可选，代码级并行 worker 数；`None/1` = 串行，`>1` = 并行 |
| `progress` | 可选，`True` 时显示环境感知代码级进度条 |

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `index_code_raw` | str | 指数代码（天软形式） |
| `index_ts_code` | str | 指数标准代码 |
| `con_code_raw` | str | 成份证券代码（天软形式） |
| `con_ts_code` | str | 成份证券标准代码 |
| `trade_date` | date | 查询日 |
| `extend_flag` | bool | 是否启用 ExType=1 扩展模式 |

> FAQ 参考：天软 FAQ id=12534（GetBKByDate 与 ExType 语义）。

---

### index_weight — 指数指定日成份权重

封装天软 `GetBkWeightByDate(板块代码, 日期)`，按日返回该指数当日的成份股及权重(%)。
**注意：** 权重数据在历史早期可能不完整，且并非所有指数都提供历史权重；建议先用 `index_basic_ext` 确认指数支持。

```python
df = td.index_weight(
    codes=["000300.CSI"],
    trade_date="20210531",
    max_workers=4,  # 可选：并行处理多个指数代码
    progress=True,  # 可选：显示环境感知代码级进度条
)
```

`index_weight` 与 `index_member_snapshot` 一样，属于按代码调用自定义 TSL 函数的接口，不使用 `code_batch_size`；需要加速多指数查询时，直接传 `max_workers>1` 即可。

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `index_code_raw` / `index_ts_code` | str | 指数代码 |
| `con_code_raw` / `con_ts_code` | str | 成份证券代码 |
| `con_name` | str | 成份证券名称 |
| `weight_pct` | float | 当日权重(%) |
| `trade_date` | date | 查询日 |

---

## 8 期货数据

### future_basic_ext — 期货合约基本信息

```python
df = td.future_basic_ext(codes=None, fields=None, refresh=False, cache=True)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `source_code` | str | 天软原始代码 |
| `ts_code` | str | 标准代码（自动计算） |
| `contract_code_raw` | str | 合约代码 |
| `change_date` | date | 变动日 |
| `product_code` | str | 交易代码（品种） |
| `delivery_year` | int | 交割年份 |
| `delivery_month` | int | 交割月份 |
| `product_name` | str | 交易品种名称 |
| `contract_multiplier` | float | 合约乘数 |
| `contract_multiplier_unit` | str | 合约乘数单位 |
| `quote_unit` | str | 报价单位 |
| `min_price_change` | float | 最小变动价位 |
| `daily_price_limit_down_pct` | float | 每日价格最大波动下限(%) |
| `daily_price_limit_up_pct` | float | 每日价格最大波动上限(%) |
| `last_trade_date` | date | 最后交易日 |
| `last_delivery_date` | date | 最后交割日 |
| `min_trade_margin_pct` | float | 最低交易保证金(%) |
| `delivery_method` | str | 交割方式 |
| `exchange_name` | str | 上市地 |
| `future_category` | str | 期货类别 |
| `commodity_category` | str | 商品期货类别 |
| `benchmark_code` | str | 基准代码 |

### future_product_mapping_ext — 期货品种代码对照表

```python
df = td.future_product_mapping_ext(codes=None, fields=None, refresh=False, cache=True)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `source_code` | str | 天软原始代码 |
| `product_code` | str | 品种代码 |
| `change_date` | date | 变动日 |
| `product_name` | str | 品种名称 |
| `main_contract_code` | str | 主力合约代码 |
| `main_contract_code_2` | str | 主力合约代码2 |
| `secondary_main_contract_code` | str | 次主力合约代码 |
| `index_contract_code` | str | 指数线代码 |
| `continuous_contract_code` | str | 连续代码 |
| `continuous_contract_code_1` | str | 连一代码 |
| `continuous_contract_code_2` | str | 连二代码 |
| `continuous_contract_code_3` | str | 连三代码 |
| `continuous_contract_code_4` | str | 连四代码 |

---

## 9 期权数据

### option_basic_daily_ext — 期权合约基本信息（每日）

```python
df = td.option_basic_daily_ext(
    codes=td.option_codes(trade_date="2024-01-02"),
    trade_date="2024-01-02",
)
```

**输出字段**

| 列名 | 类型 | 说明 |
|------|------|------|
| `source_code` | str | 天软原始代码 |
| `contract_code_raw` | str | 合约原始代码（自动计算） |
| `ts_code` | str | 标准代码（自动计算） |
| `underlying_ts_code` | str | 标的证券标准代码（自动计算） |
| `trade_date` | date | 截止日 |
| `contract_trade_code` | str | 合约交易代码 |
| `contract_short_name` | str | 合约简称 |
| `underlying_code_raw` | str | 标的证券代码（原始） |
| `underlying_name` | str | 标的证券名称 |
| `underlying_type` | str | 标的证券类型 |
| `exercise_style` | str | 行权方式（欧式/美式） |
| `option_type` | str | 期权类型（认购/认沽） |
| `contract_unit` | float | 合约单位 |
| `exercise_price` | float | 行权价 |
| `first_trade_date` | date | 首个交易日 |
| `last_trade_date` | date | 最后交易日 |
| `exercise_date` | date | 行权日 |
| `exercise_delivery_date` | date | 行权交割日 |
| `maturity_date` | date | 到期日 |
| `open_interest` | float | 合约未平仓数 |
| `pre_close` | float | 合约前收盘价 |
| `pre_settle` | float | 合约前结算价 |
| `underlying_pre_close` | float | 标的前收盘价 |
| `upper_limit_price` | float | 涨幅上限价格 |
| `lower_limit_price` | float | 跌幅下限价格 |
| `unit_margin` | float | 单位保证金 |
| `margin_param_1_pct` | float | 保证金计算比例参数一(%) |
| `margin_param_2_pct` | float | 保证金计算比例参数二(%) |
| `round_lot` | float | 整手数 |
| `contract_status` | str | 期权合约状态信息 |
| `open_position_status` | str | 开仓状态 |
| `exchange_name` | str | 上市地 |

---

## 10 TinyClient 直接接口

```python
import tinydata as td
from tinydata import TinyClient

td.configure(user="user", password="pass", opi_url="http://your-opi-host:8888")

# 直接复用当前全局配置
client = TinyClient(td.get_config())
# 或使用默认客户端
client2 = td.get_client()
```

### 顶层包装：query_infotable

```python
df = td.query_infotable(
    table_id=126,              # 天软数据表 ID
    codes=["SZ000001"],        # 证券代码列表
    start_date="2024-01-01",   # 开始日期
    end_date="2024-03-31",     # 结束日期
    fields=None,               # 返回字段（None = 全部）
    date_field="截止日",        # 日期过滤字段名
    as_of_date="2024-03-31",    # 可选：写入 pn_date()，用于控制财务数据时点口径
    report_mode=0,              # 可选：写入 pn_ReportMode()；-1 全部，0 调整后/最新，1 调整前
    allow_full_table=False,      # 无 codes 时必须显式设为 True 才允许全表查询
    code_batch_size=100,         # 可选：每批提交的代码数
    max_workers=None,            # 可选：InfoTable 代码批次并行 worker 数
    progress=None,               # 可选：None = 自动；交互式环境默认开，脚本环境默认关
)
# 返回: pd.DataFrame（已按请求字段返回）
```

对按代码分批执行的 InfoTable 查询，`max_workers>1` 可并行处理多个代码批次；`progress=None` 时交互式环境默认开启、脚本环境默认关闭，显式传 `progress=True/False` 可覆盖默认行为。启用后，终端里会显示 tqdm 风格进度条，IPython/Jupyter 会优先显示 notebook 友好的进度条。命中本地缓存或走 no-code 全表查询时，通常不会显示进度条。若并行批次触发 OPI 429，tinydata 会自动降低 `max_workers` 并重试失败批次；若环境缺少 tqdm，则回退到原来的 stderr 文本进度条。

### 顶层包装：query_market

```python
df = td.query_market(
    symbol="SZ000001",
    start_time="2024-01-01",
    end_time="2024-03-31",
    cycle="日线",
    fields=["date", "StockID", "close"],
)
```

### TinyClient.exec — 直接执行 TSL

```python
df = client.exec(
    'return select ["StockID"], ["证券代码"] from infotable 302 of "开放式基金" end;'
)
```

### TinyClient.call — 调用服务端函数

```python
df = client.call(
    "MyServerFunc",
    {"code": "SZ000001"},
)
```

### TinyClient.query — 单标的行情查询

```python
df = client.query(
    stock="SZ000001",
    cycle="日线",
    begin_time="2024-01-01",
    end_time="2024-03-31",
    fields=["date", "StockID", "close"],
)
```

### TinyClient.query_panel — 多标的行情查询

```python
df = client.query_panel(
    stocks=["SZ000001", "SH600000"],
    cycle="日线",
    begin_time="2024-01-01",
    end_time="2024-03-31",
    fields=None,
    code_kind="stock",
    adjust="complex",
    adjust_date="2024-03-31",
)
```

---

## 11 错误处理

```python
import tinydata as td
from tinydata.errors import (
    TinyDataError,           # 所有异常的基类
    TinyDataAuthError,       # 认证失败（401/403）
    TinyDataConfigError,     # 配置无效或缺失
    TinyDataDependencyError, # 可选依赖缺失
    TinyDataQueryError,      # 查询执行失败
    TinyDataRateLimitError,  # OPI 429：并发/请求数超限，自动重试后仍失败
    TinyDataTimeoutError,    # 请求超时
    TinyDataParameterError,  # 参数不合法（含 safe_query 触发）
    TinyDataCodePoolError,   # 代码池为空或不可用
)

try:
    df = td.stock_daily(codes=["SZ000001"])  # 缺少日期参数
except TinyDataParameterError as e:
    print(f"参数错误: {e}")
except TinyDataRateLimitError as e:
    print(f"OPI 并发或请求数超限: {e}")
except TinyDataTimeoutError as e:
    print(f"请求超时: {e}")
except TinyDataQueryError as e:
    print(f"查询失败: {e}")
```

### 错误层次

```
TinyDataError
├── TinyDataDependencyError   # 可选依赖缺失
├── TinyDataConfigError       # 配置无效或缺失
├── TinyDataAuthError         # 身份认证
├── TinyDataTimeoutError      # 请求超时
├── TinyDataQueryError        # TSL 查询执行
│   └── TinyDataRateLimitError # HTTP 429 并发/请求数超限
├── TinyDataCodePoolError     # 代码池无法解析
└── TinyDataParameterError    # 参数验证（含 safe_query）
```

---

## 12 缓存管理

数据集缓存默认位于 `~/.tinydata/cache/dataset/<dataset>/<sha256>.parquet`，代码池缓存位于 `~/.tinydata/cache/universe/<name>/<sha256>.parquet`。

### 控制缓存行为

```python
# 不使用缓存（实时查询）
df = td.stock_daily(codes=[...], start_date="2024-01-01", end_date="2024-01-31", cache=False)

# 强制刷新（忽略现有缓存，重新查询并写入）
df = td.stock_daily(codes=[...], start_date="2024-01-01", end_date="2024-01-31", refresh=True)

# 修改缓存目录
td.configure(cache_dir="D:/tinydata-cache")
```

### 清理缓存

当前版本**没有**公开的 `clear_cache()` 或 TTL 配置接口。需要清理缓存时，请直接删除 `cache_dir` 下对应目录，例如：

- `~/.tinydata/cache/dataset/stock_daily/`
- `~/.tinydata/cache/universe/stock/`

缓存 key 由数据集名、查询字段、日期范围、代码列表、批量大小等参数共同决定，参数变化会自动落到不同缓存文件。

---

## 13 查询参数约定

### 通用参数

所有数据集函数共享以下参数：

| 参数 | 类型 | 说明 |
|------|------|------|
| `codes` | list[str] | 天软格式代码列表；None = 使用默认代码池 |
| `start_date` | str/date | 起始日期，格式 `"YYYY-MM-DD"` |
| `end_date` | str/date | 结束日期 |
| `trade_date` | str/date | 单日查询（与 start/end 互斥） |
| `report_period` | str/date | 报告期（财务数据，如 `"2023-12-31"`） |
| `all_history` | bool | `True` = 查全量历史（跳过 safe_query 检查） |
| `fields` | list[str] | 指定返回列；None = 全部列；可传数据字典原始字段名，未登记字段会保留原名 |
| `refresh` | bool | `True` = 强制刷新缓存 |
| `cache` | bool | `False` = 不使用缓存 |
| `code_batch_size` | int | 每批次提交的代码数量 |
| `max_workers` | int | 代码批次并行 worker 数；`None/1` = 串行，`>1` = 并行批次执行 |
| `progress` | bool/None | `None` = 自动；交互式环境默认开，脚本环境默认关。显式传 `True/False` 可覆盖；命中缓存时通常不显示 |
| `max_codes` | int | 最多处理的代码数（调试/采样用） |
| `report_mode` | int | 财务表可选，写入天软 `pn_ReportMode()`：`0` 调整后/最新，`1` 调整前，`-1` 调整前和调整后全部记录 |
| `as_of_date` | str/date | 财务/定报表可选，写入天软 `pn_date()`；可与 `report_period` 组合表达“某报告期截至某日可见” |

对财务数据，`report_period` 与 `start_date/end_date` 语义不同：`report_period` 按 `截止日` 过滤报告期；`start_date/end_date` 默认按接口定义的披露时点字段过滤，股票三大表和主要财务指标通常是 `公布日`。tinydata 在按披露时点窗口查询时会把 `end_date` 写入 `pn_date()`，使结果更接近“截至该日已可见”的 PIT 口径；按 `report_period` 查询时不把报告期强行作为 `pn_date()`，避免把尚未公告的报告期误当成可见时点。需要同时约束报告期和可见时点时，传 `report_period="20231231", as_of_date="20240430"`。

对股票财务链、基金净值/持仓/配置链这类高体量 InfoTable 数据集，建议优先组合使用较小的 `code_batch_size`、`max_workers>1` 和 `progress=True`，兼顾吞吐和可观测性。

### 字段命名约定

| 规律 | 示例 | 说明 |
|------|------|------|
| `tsl_code` | `SZ000001` | 天软原生代码 |
| `ts_code` | `000001.SZ` | 标准市场格式（自动计算） |
| `*_date` | `trade_date` | `datetime.date` 类型 |
| `*_pct` | `roe_pct` | 百分比浮点数（25.3 表示 25.3%） |
| `*_ratio_pct` | `float_ratio_pct` | 比率百分比 |
| `*_amount` | `buy_amount` | 金额（元） |
| `*_volume` | `short_balance_volume` | 数量/股数 |
| `*_mv` | `stock_mv` | 市值（元） |
| `*_raw` | `bond_code_raw` | 原始未处理代码字符串 |

---

## 14 开发与测试

### 运行测试

```bash
# 全部测试（含 mock）
python -m pytest

# 只运行不需要天软连接的测试
python -m pytest -m "not requires_tinysoft"

# 查看详细输出
python -m pytest -v --tb=short
```

### 开发模式安装

```bash
pip install -e ".[test]"
```

### 代码结构

```
src/tinydata/
├── __init__.py          # 公共 API 入口（导出所有函数）
├── config.py            # 配置加载与优先级处理
├── client.py            # TinyClient HTTP 客户端
├── cache.py             # 缓存引擎（SHA256 + parquet）
├── universe.py          # 代码池函数
├── market.py            # 市场行情层（markettable）
├── errors.py            # 异常层次
└── datasets/
    ├── specs.py         # DatasetSpec + dataset_api 装饰器
    ├── stock.py         # 股票数据集（45+ 个）
    ├── fund.py          # 基金数据集（30+ 个）
    ├── bond.py          # 债券数据集（1 个）
    ├── index.py         # 指数/日历数据集（4 个）
    ├── future.py        # 期货数据集（2 个）
    └── option.py        # 期权数据集（1 个）
```

### 添加新数据集

1. 在对应 `datasets/*.py` 中定义 `DatasetSpec`：

```python
MY_DATASET = register_dataset(
    DatasetSpec(
        name="my_dataset",
        domain="stock",
        priority="P1",
        table_id=999,
        source_table_name="股票.我的表",
        code_kind="stock",
        code_pool="stock",
        field_mapping={"StockID": "tsl_code", "截止日": "trade_date", ...},
        date_columns=("trade_date",),
        numeric_columns=(...),
        safe_query_required=True,
    )
)

my_dataset = dataset_api(MY_DATASET)
```

2. 在 `__all__` 列表中添加。
3. 在 `src/tinydata/__init__.py` 的 import 列表中添加。
4. 在 `docs/usage.md` 中补充文档。

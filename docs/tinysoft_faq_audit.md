# TinySoft FAQ 对照审计

审计日期：2026-05-26

输入资料：

- `references/天软数据提取常见FAQ.xlsx`
- 工作簿内 80 条 FAQ 链接和“更多资料”6 条链接
- TinySoft FAQ/函数文档网页，例如：
  - [天软有哪些系统参数](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17345)
  - [天软的复权方式](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=12533)
  - [如何设置复权日](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=10998)
  - [财务数据的调整前与调整后的表格数据提取：pn_reportmode()](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17796)
  - [财务数据提取时 pn_ReportMode() 与 pn_date() 对数据结果的影响](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17811)
  - [天软基金定期报告取数代码说明](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17867)
  - [MarketTable](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=1889)
  - [TradeTable](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=1890)
  - [如何提取指数历史成份股](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=12534)
  - [如何提取指数历史成份股权重](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=12535)

## 总体结论

tinydata 的核心方向是正确的：稳定数据集优先走 `infotable`，行情走 `markettable`，代码池、批量、缓存和字段标准化都符合 TS-OPI 直连库的定位。但 FAQ 对照后，发现以下必须修正或明确的点：

1. `Pn_rateday()` 不只是日期，还支持 `-1` 和 `0` 两个特殊值。已修正：`adjust_date=-1` 表示上市日/成立日后复权口径，`adjust_date=0` 表示天软当前/最后口径。
2. 财务 `report_period` 不能套用到 `公布日` 过滤。已修正：如果数据表存在 `截止日`，`report_period` 按 `截止日` 过滤；`start_date/end_date` 仍按数据集定义的披露时点字段过滤。
3. FAQ 明确 `pn_date()` 会影响财务调整前/调整后和 PIT 结果。已修正：按披露时点窗口查询时，将 `end_date` 写入 `pn_date()`；同时新增 `report_mode` 参数透传 `pn_ReportMode()`。
4. `getbk("A股")` 是当前板块，不等于历史股票全集。已修正：`stock_codes(include_inactive=True)` 优先查询 `股票.基本信息` 全表，避免漏退市股票；当前板块仅作为兜底。
5. 市场交易日历 FAQ 包含国内期货市场代码 `QI000001`。已修正：`market_codes()` 加入 `QI000001`，并补充市场名称映射。

仍建议后续升级：

- P1：基金定期报告类接口应支持“基金主代码/母基金代码”归一化，否则 A/C 类、分级基金代码会出现查不到或重复。
- P1：~~新增 `index_weight()`~~ **已实现**：`td.index_weight(codes, trade_date)` 封装 `GetBkWeightByDate`，按日返回成份权重(%)。
- P1：~~新增指数/板块“指定日成份快照”接口~~ **已实现**：`td.index_member_snapshot(codes, trade_date, extend=False)` 封装 `GetBKByDate(index_id, date, ex_type)`，与历史版本表 `index_member_versioned` 区分。
- P2：~~新增基金复权净值接口~~ **已实现**：`td.fund_adjusted_nav(codes, start_date, end_date, adjust=1, adjust_date=-1)` 封装 `FundNAWByRateBegtEndt`，支持前/后复权及自定义基准日。
- P2：新增 `tradetable`/逐笔/盘口/集合竞价高频接口前，需要单独的高容量保护、字段说明和分页策略。
- P2：~~新增基金复权净值接口应使用 `FundNAWByRateBegtEndt`~~ **已实现**（见上）。
- P2：补充 `Report`、`ReportOfAll`、`Last12MData`、`LastQuarterData` 等点查财务函数，尤其 TTM 不能用于资产负债表类时点指标。

## 逐条对照

| 行 | FAQ | 对 tinydata 的结论 |
|---:|---|---|
| 2 | [天软有哪些系统参数](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17345) | 已覆盖 `pn_cycle`、`pn_rate`、`pn_rateday`、`pn_date`、`pn_ReportMode` 的核心取数路径；其他系统参数保留给 `TinyClient.exec()` 直接 TSL。 |
| 3 | [天软的复权方式](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=12533) | 已覆盖：`adjust=0/1/2` 分别对应不复权、比例复权、复杂复权。 |
| 4 | [如何设置复权日](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=10998) | 已修正：支持 `adjust_date=-1`、`0` 和具体日期，并在文档中明确前复权/后复权/定点复权。 |
| 5 | [天软自由周期](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=15109) | 部分覆盖：可直接传 `cy_trailingdays(...)` 等原生周期表达式；未封装 `Pn_FreeCycle()`。 |
| 6 | [pn_viewpoint 的正确使用方式](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17596) | 未封装。FAQ 显示该参数性能成本很高，适合通过 `TinyClient.exec()` 显式使用。 |
| 7 | [with 设置系统环境变量](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=15020) | API 内部按查询拼独立 TSL，不依赖会话全局状态；复杂 `with` 语句可用 `TinyClient.exec()`。 |
| 8 | [怎么临时设置系统参数](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=15228) | 已在 market/infotable 查询中显式写入必要系统参数；任意参数临时设置可用直接 TSL。 |
| 9 | [天软公用市场板块说明](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17324) | 部分覆盖：代码池使用部分板块；未提供通用 `getbk/getbklist` API。 |
| 10 | [分类板块如何获取所有个券](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17966) | 需谨慎：FAQ 说明很多板块只代表当前状态；已修正 A 股代码池，其他板块暂未通用化。 |
| 11 | [如何得到历史 A 股](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=11006) | 已修正：默认股票代码池不再只依赖当前 `A股` 板块；并通过 `index_member_snapshot` 提供 `GetBKByDate` 快照接口。 |
| 12 | [板块名称转指数代码](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=15021) | 未覆盖；可作为板块工具 API 后续扩展。 |
| 13 | [概念板块](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17438) | 未覆盖；缺少概念板块代码和历史成份接口。 |
| 14 | [股票与基金分类属性代码](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=31492) | 部分覆盖：`stock_industry_versioned`、`fund_classification_info/member` 已提供基础表。 |
| 15 | [股票行业分类说明](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17998) | 部分覆盖：表 139 已接入；层级展开和指定体系筛选可进一步增强。 |
| 16 | [申万行业使用概览](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=31499) | 部分覆盖：申万字段和行业分类表可取；缺少申万专用便捷接口。 |
| 17 | [指定日个股申万一级行业](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=15216) | 未提供单点便捷函数；可由 `stock_industry_versioned` 过滤实现。 |
| 18 | [申万一二三级归属与指数代码对照](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17258) | 未覆盖；建议新增行业层级/指数代码对照表接口。 |
| 19 | [申万行业变更连续性](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=19840) | 未覆盖；需要专门的行业版本桥接逻辑。 |
| 20 | [Base](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=29053) | 未封装 `Base()` 点查函数；基础信息主要通过 `infotable` 数据集取数。 |
| 21 | [Python 基本面提取范例](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17212) | 核心能力已由 dataset API 覆盖。 |
| 22 | [证券数据专家/板块数据专家](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=11014) | 属于字段发现工具；tinydata 通过显式 `DatasetSpec` 管理字段。 |
| 23 | [pn_reportmode 调整前/调整后](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17796) | 已升级：`report_mode=-1/0/1` 透传到 `pn_ReportMode()`。 |
| 24 | [pn_ReportMode 与 pn_date 的影响](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17811) | 已升级：披露时点窗口查询会写入 `pn_date=end_date`；文档补充 PIT 语义。 |
| 25 | [报告期推导函数汇总](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17318) | 未封装 `NewReportDate...` 类函数；可后续做财务点查工具。 |
| 26 | [截止日、数据报告期、公布日区别](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17264) | 已修正：`report_period` 按 `截止日`；`start_date/end_date` 用披露时点字段。 |
| 27 | [正确匹配财务公布日](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=19870) | 部分覆盖：有公布日字段的表已映射；缺少对基金部分表公布日缺失/为 0 时的自动补表逻辑。 |
| 28 | [查找财务指标 ID](http://www.tinysoft.com.cn/tsdn/helpdoc/index.tsl?type=10001) | 未覆盖；建议后续提供字段/指标搜索工具。 |
| 29 | [哪些财务数据可以取最近 12 个月](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=18002) | 未封装 `Last12MData()`；文档应提醒 TTM 不适用于资产负债表类时点指标。 |
| 30 | [基金定期报告取数代码说明](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17867) | 需升级：基金定报表应按主代码/母基金代码归一化。 |
| 31 | [Report](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=29045) | 未封装点查函数；普通表数据由 `infotable` 支持。 |
| 32 | [ReportOfAll](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=29046) | 未封装实时计算财务指标点查。 |
| 33 | [InfoArray](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=29055) | `query_infotable` 是相近的表查询方式，并保留 `StockID`/`StockName`。 |
| 34 | [InfoArrayExt](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=29056) | 未封装字段阈值扩展函数；可用 `extra_where` 在内部能力层实现，但未公开。 |
| 35 | [Last12MData](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=29052) | 未覆盖。 |
| 36 | [LastQuarterData](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=29051) | 未覆盖。 |
| 37 | [Python 财务提取范例](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17213) | 部分覆盖：常用财务表已做 dataset API；点查函数和 TTM 尚缺。 |
| 38 | [取个股截面数据](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17203) | 已覆盖：`query_market_panel(..., trade_date=...)`。 |
| 39 | [取个股时间序列数据](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17204) | 已覆盖：`stock_daily/weekly/monthly` 和 `query_market_panel`。 |
| 40 | [取组合截面数据](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17205) | 已覆盖：`codes=[...]` 批量取数。 |
| 41 | [取组合时间序列数据](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17206) | 已覆盖：批量 `markettable`。 |
| 42 | [夜盘合约完整一天高频数据](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=15589) | 部分覆盖：可传精确时间窗口；未提供夜盘交易日切分助手。 |
| 43 | [股票集合竞价数据](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17328) | 未提供专用接口；可作为高频/盘口扩展。 |
| 44 | [实盘批量提取 A 股盘口](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=19839) | 未覆盖实时盘口；tinydata 当前是拉取式 OPI。 |
| 45 | [如何提取证券行情数据](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=10996) | 已覆盖 `markettable` 主流程。 |
| 46 | [提取复权后的收盘价](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=10997) | 已覆盖：`adjust` + `fields=["close"]`。 |
| 47 | [期货数据提取](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17346) | 部分覆盖：`future_daily` 和期货基本信息；连续/主力/排名数据未全覆盖。 |
| 48 | [多头/空头持仓排名](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=15029) | 未覆盖。 |
| 49 | [RTD 行情订阅](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=15278) | 超出当前库范围。 |
| 50 | [行情主动推送第三方接口](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=15507) | 超出当前库范围。 |
| 51 | [合理下载大量高频行情](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17210) | 部分覆盖批量和缓存；缺少高频下载任务管理与限流文档。 |
| 52 | [客户端下载高频到本地](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=31535) | 超出当前 TS-OPI 直连库范围。 |
| 53 | [Python 行情提取范例](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17211) | 已覆盖主要行情 API。 |
| 54 | [Python 分批导入本地](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=18745) | 部分覆盖：内置 parquet 缓存；未提供数据库导入工具。 |
| 55 | [高频、超高频数据说明](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=10999) | 部分覆盖：可请求原始字段；未完整文档化高频字段。 |
| 56 | [行情盘口字段说明](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17422) | 未标准化盘口字段。 |
| 57 | [Level 1 与 Level 2 区别](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17362) | 未覆盖 L2 特有接口。 |
| 58 | [期货交易性质算法](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=32289) | 未覆盖。 |
| 59 | [期货主力与连续合约复权算法](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17782) | 未专门覆盖；不能仅按股票复权逻辑假设。 |
| 60 | [可转债复权说明](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=30783) | 未专门验证；`cbond_daily(adjust=...)` 需真实连接测试确认。 |
| 61 | [基金复权净值提取与算法](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=18021) | **已实现**：`fund_adjusted_nav` 封装 `FundNAWByRateBegtEndt`，支持 `adjust` (1=后复权/2=前复权) 与 `adjust_date` (-1/0/具体日)。 |
| 62 | [资金流向统计](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=15453) | 未覆盖。 |
| 63 | [期货连续合约换月涨幅处理](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=15181) | 未覆盖。 |
| 64 | [基金折价率/折溢率](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=19896) | 未覆盖。 |
| 65 | [银行间债券全价与到期收益率](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=33020) | 未覆盖。 |
| 66 | [Close() 系列函数](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=28806) | 行情价格由 `markettable` 覆盖；未封装 `close()` 指标函数。 |
| 67 | [Nday](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=28975) | 未封装；时间序列用 `markettable datekey`。 |
| 68 | [rd](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=28805) | 未封装。 |
| 69 | [MarketTable](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=1889) | 已覆盖核心语法。 |
| 70 | [TradeTable](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=1890) | 未覆盖；建议新增独立 `query_trade_table`，并默认要求精确时间窗口。 |
| 71 | [交易日序列及交易天数模型](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=19847) | 部分覆盖：表 753 日历；已补 `QI000001`。交易日推移函数未封装。 |
| 72 | [交易日推移方式](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=15024) | 未封装。 |
| 73 | [各证券品种日内时间段](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=15506) | 未覆盖。 |
| 74 | [指数历史成份股](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=12534) | **已覆盖**：表 752 提供历史成份版本（`index_member_versioned`）；`index_member_snapshot` 封装 `GetBKByDate` 及 `ExType` 扩展模式。 |
| 75 | [可提取成份股的指数及开始日期](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=18013) | 未固化覆盖清单；可作为文档引用。 |
| 76 | [指数历史成份股权重](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=12535) | **已实现**：`index_weight` 通过 `GetBkWeightByDate` 返回指定日成份权重(%)。 |
| 77 | [成份股权重指数覆盖范围](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=15262) | 已配合 `index_weight` 提供查询入口；具体覆盖清单仍以官方为准（部分早期日期/指数可能无权重数据）。 |
| 78 | [指数估值数据覆盖](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17307) | 未覆盖指数估值系列表。 |
| 79 | [天软数据开始时间](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=12537) | 未文档化数据起始时间；建议在数据集元数据中增加 coverage notes。 |
| 80 | [宏观数据](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=15274) | 未覆盖宏观数据。 |
| 81 | [常用取数范例](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=18750) | 部分覆盖：常用行情、基本面、财务 API 已有；高级模型未覆盖。 |
| 更多 1 | [天软数据字典](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17496) | tinydata 当前以手工 `DatasetSpec` 固化高优先级字段；后续可做字段发现/校验工具。 |
| 更多 2 | [各类数据更新、提取专题文档汇总](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=30658) | 作为后续版本巡检来源。 |
| 更多 3 | [数据模型及相关应用专题汇总](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=31420) | 作为扩展模型来源。 |
| 更多 4 | [数据相关 FAQ 汇总](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=10987) | 本次 FAQ 的上级索引。 |
| 更多 5 | [取数建模相关 FAQ 汇总](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=11010) | 后续建模接口设计参考。 |
| 更多 6 | [教学视频](http://www.tinysoft.com.cn/tsdn/tstrain/index.tsl) | 非接口文档，未纳入代码实现。 |


# TinySoft 股票/基金远端资料对照审计

审计日期：2026-05-26

输入资料：

- `references/【天软】远端基金数据、模型、FAQ汇总.xlsx`
- `references/【天软】远端股票数据、模型、FAQ汇总.xlsx`
- 两个工作簿内的非视频 TSDN 链接共 320 个，其中 319 个可访问。

关键网页依据包括：

- [基金基本信息](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17658)
- [基金开放式基金费率](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17662)
- [基金净值增长率与基准比较](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17664)
- [基金资产负债表](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17666)
- [基金收益及分配](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17667)
- [ETF 申购赎回 PCF FAQ](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=11108)
- [股票发行上市](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17551)
- [股票行业分类信息](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17963)
- [证券交易时间](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17525)
- [股票十大股东](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=17576)
- [境外投资者持股信息](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=32080)
- [股票非经常性损益](http://www.tinysoft.com.cn/tsdn/helpdoc/display.tsl?id=19875)

## 总体结论

之前的数据实现主线是合理的：普通稳定表继续走 `InfoTable`，行情走 `MarketTable`，模型/函数型接口不伪装成普通表。此次股票/基金专项资料对照后，确认了两类需要升级的点：

1. 基金定期报告类表的取数代码规则需要进入数据逻辑。多张表明确要求非分级基金用“不同收费模式基金主代码”，分级基金用“母基金代码”。已在相关基金定报接口中自动转换。
2. 工作簿中有一批高频使用、字段稳定、真实 OPI 可验证的表此前未暴露为便捷 API。已新增股票/基金接口并补充真实 OPI 测试。

## 已新增或升级的接口

基金：

- `fund_benchmark`：基金.业绩比较基准，表 303。
- `fund_fee`：基金.开放式基金费率，表 309；注意 `公布日`、`生效日` 可能为 0。
- `fund_nav_benchmark_return`：基金.净值增长率与基准比较，表 311。
- `fund_balance_sheet`：基金.资产负债表，表 312。
- `fund_income_statement`：基金.收益及分配，表 314。
- `fund_buy_sell`：基金.累计买入和卖出，表 319。
- `fund_dividend`：基金.分红，表 326。
- `fund_split`：基金.份额拆分，表 327。
- `fund_namechange`：基金.基金信息变更，表 359。
- `fund_etf_sub_redemption`：ETF 申购赎回基本信息，表 346。
- `fund_etf_constituent`：封装 `GetFundETFConstituent`，用于指定日 ETF PCF 成分股。

股票：

- `stock_ipo`：股票.发行上市，表 12。
- `stock_delist_solution`：股票.终止上市股份处理方案，表 17。
- `stock_classification_info`：股票.股票行业分类信息，表 138。
- `stock_top10_holder`：股票.十大股东，表 24。
- `stock_top10_float_holder`：股票.十大流通股东，表 26。
- `stock_controller`：股票.控股股东及实际控制人，表 29。
- `stock_officer_hold_change`：股票.董事、监事、高管持股变动，表 30。
- `stock_foreign_holding`：股票.境外投资者持股信息，表 31。
- `stock_nonrecurring`：股票.非经常性损益，表 150。
- `stock_trade_time`：股票.证券交易时间，表 137。

同步升级：

- `DatasetSpec` 增加 `code_transform` 元数据。
- 对基金持股、行业配置、资产配置、债券配置、持债、交易席位以及新增定报表启用基金主代码/母基金代码转换。
- `README.md`、`docs/usage.md` 补充新增接口、ETF PCF、基金定报代码规则。
- `tests/test_datasets.py` 增加新增字段映射和基金主代码转换单元测试。
- `tests/test_real_opi.py` 增加新增接口真实 OPI 覆盖。

## 暂缓接口

以下资料有价值，但暂不作为本轮稳定 API：

- 股票自由流通类数据：TSDN 2025-11-25 文档说明需要联系商务授权，未纳入默认稳定接口。
- `tradetable`、盘口、Level 2、集合竞价、夜盘高频：需要分页、限流和字段分级策略。
- 股票配股、增发、优先股、证券主表等：资料已确认，但本轮优先实现研究/回测中更常用且测试样本稳定的接口；这些可作为下一批 P1/P2 扩展。

## 第三轮新增接口（已实现并通过真实 OPI 验证）

- `index_weight(codes, trade_date)`：封装 `GetBkWeightByDate`，返回指定日的指数成份股权重(%)。FAQ id=12535/15262。
- `index_member_snapshot(codes, trade_date, extend=False)`：封装 `GetBKByDate(板块代码, 日期, ExType)`，返回指定日成份股快照，与版本表 `index_member_versioned` 互补。FAQ id=12534。
- `fund_adjusted_nav(codes, start_date, end_date, adjust=1, adjust_date=-1)`：封装 `FundNAWByRateBegtEndt`，提供后/前复权净值序列，含 `adjusted_nav`、`adjust_factor`、`adjusted_return_pct` 等核心字段。FAQ id=18021。

## 验证

已为新增接口设计 mock 单元测试和真实 OPI 参数化测试。真实 OPI 测试使用环境变量中的天软账号密码，运行命令为：

```bash
$env:TINYDATA_RUN_REAL_OPI='1'; python -m pytest
```


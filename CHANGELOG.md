# Changelog

## [v0.19] - 2026-06-01 — PR 公式第三次修正：前瞻性穿透回报率

### Added
- **可支配现金计算器** (`disposable_cash.py`): 经营CF - 投资流出 - 财务费用 + 货币资金 - 限制性货币 - 短期借款 + 交易性金融资产
- **Web+LLM 轻量提取器** (`web_extractor.py`): Layer 3 数据源，提取分红承诺和回购注销公告
- `DataPoolOrchestrator._fetch_web_extractions()`: 数据获取阶段新 Layer，提取结果写入 StockDataBundle
- `StockDataBundle` 新增 3 字段: `dividend_commitment`, `buyback_cancellation`, `restricted_cash`

### Changed
- **PR 公式根性重写**: `(可支配现金 × 分配比率 × 0.90 + 回购注销) / 当前市值`
  - 分母从历史市值改为当前市值（前瞻性估值）
  - 分子从历史分红改为可支配现金 × 分配比率
  - 分配比率两级降级: 公告承诺×0.8 / 历史外推×0.7
  - 回购注销 Web+LLM 提取，只算确认注销的部分
- `pr_calculator.py` 完全重写: 移除 PRYearDetail/逐年计算，使用 v0.19 前瞻公式
- `oe_calculator.py` 简化: 删除路径A（OE_income）+ 质量验证 5→4 级

### Removed
- OE 路径A（利润表视角 OE_income）: 折旧用 CAPEX×0.55 估计，数据不可靠
- OE 质量验证第5项（利润→现金转化率）: 输入不可靠则输出无意义

### Fixed
- **CAGR bug**: 3 个数据点→2 个增长期间，`**(1/3)` → `**(1/2)`（影响 oe_calculator + l5_calculator 共 3 处）
- **可支配现金单位**: Tushare 元→万元转换（与分红单位对齐）

### 茅台验证
- PR 1.87% (v0.17: 2.24%), 分配比率 74.9%(历史外推), 可支配现金 454 亿, Final 11.06 备选池


## [Unreleased] v0.17

### Fixed
- **PR 公式根性修正**：穿透回报率从「OE_cf_median / 市值」改为「(全年分红总额 + 回购注销金额) / 年末总市值」
  - 分红按财务年度(end_date)汇总，含中期+年末所有公告
  - 回购数据来源: Tushare repurchase 接口，筛选 proc='实施/完成'
  - 取 5 年中位数，与三级阈值 (12%/8%/5%) 对比
  - OE 保留用于质量验证扣分，不再参与 PR 本身计算
- **分红验证器年度汇总 bug 修复**：`_fetch_dividends` 从逐条 append 取均值 → 按年 sum 汇总

### Added
- `tushare_client.py`: 新增 `repurchase()` 方法（≥600积分）
- `pr_calculator.py`: 新增 `PRYearDetail` dataclass 记录逐年分红/回购/市值/PR明细
- `turtle_constants.yaml`: 新增 `dividend_source` / `repurchase_source` / `aggregation` / `price_point` 字段


## [v0.16] - SOTP + 回测模块

### Added
- **SOTP 双口径**：口径A(母公司可支配现金÷市值) + 口径B(合并口径×分红回流率÷市值)
- **回测验证框架**：WindowManager(Walk-Forward 滚动窗口) + DividendValidator(PR兑现率) + BacktestStatistics + BacktestReportGenerator
- 回测核心指标：PR兑现率(实际/预测≥0.7) + 阈值达标率(实际≥5%) + Top5 vs Bottom5 股息差


## [v0.15] - 2026-06-01

### Changed
- **穿透回报率重构**：双轨（粗算/精算）→ 统一精算单轨
  - OE 来源统一为现金流路径（经营CF−总CAPEX×维持系数）的5年中位数
  - 取消 HH 偏差扣分，由 OE 稳定性（CV）替代
  - PR 三级阈值：≥12%→20分, ≥8%→15分, ≥5%→10分, <5%→0分
- **OE 质量标签前置**：三级标签（🟢可信/🟡存疑×0.7/🔴不可靠→L4=0），在PR计算前生效
- **OE 双路径计算**：路径B(现金流，主)用于PR计算 + 路径A(利润表，辅)用于质量验证
- **OE 质量验证五级**：新增「利润→现金转化率」维度（路径B OE/路径A OE）

### Added
- **L5 外推可行度新增1维**：OE增长趋势(近3年CAGR)
- **价值陷阱第3项强化**：负债压力新增子触发（有息负债/EBITDA>4、EBIT/利息<3）
- 阶段一~四全面完成：156测试/81%覆盖率，~6000行代码
- 回测验证框架设计定型 (阶段五)


## [v0.14] - 2026-05-31

### Added
- 项目骨架初始化
- 3 规则 YAML (hard_gate, l2_screener, turtle_constants)
- pyproject.toml (Poetry 包管理)
- CI 配置 (GitHub Actions)

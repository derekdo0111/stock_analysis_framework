# Changelog

## [v0.27] - 2026-06-04 — 三阶段LLM统一管线：商业检索 → 分析Agent → 交叉验证

### Added
- **商业知识检索 Agent** (`business_retrieval_agent.py`): Phase 3.5，LLM + web_search tool calling 获取5类实时商业信息（商业模式/管理层/行业地位/风险监管/分红回购），标注置信度+来源URL
- **web_search 工具** (`tools.py`): Tavily/SerpAPI 搜索适配，支持 tool calling 多轮循环，定义标准 tool schema
- **三模型独立配置** (`client.py`): `LLM_RETRIEVAL_MODEL` / `LLM_ANALYSIS_MODEL` / `LLM_VALIDATION_MODEL` 三环境变量，默认均为 `deepseek-chat`，共用同一 API key
- **LLMClient.chat_with_tools()**: 多轮 tool calling 对话方法，最多5轮，自动执行搜索并回传结果
- **brief.md Section 5**: 新增「五、LLM 商业知识检索」区块，将商业检索结果作为分析 Agent 的输入上下文

### Changed
- **分析 Agent 重构** (`analysis_agent.py`): 输入从 `FinalScore + profile` 改为完整 `brief.md`（含原始数据+得分+财报洞察+商业知识），System prompt 增加「利用商业知识作为行业背景」指引
- **交叉验证 Agent 重构** (`cross_validation_agent.py`): 输入从 `brief.md` 改为 `analysis报告 + brief.md(源数据)`，验证靶子从管线得分变为分析报告结论。System prompt 改为「事实核查员」角色：✓源数据可支撑 / ⚠过度解读 / ✗与源数据矛盾 / ?缺乏证据
- **brief.md Section 4 重写**: 从「交叉验证提示」改为「分析报告撰写指引」
- **CLI 统一管线** (`cli.py`): 
  - 移除 `--llm` / `--cross-validate` / `--brief` 三个独立 flag
  - 新增 `--no-llm` 参数跳过 LLM 阶段
  - 默认走完整管线：Phase 1→2→3→3.5→4→5a→5b→6
- **Phase 3.5 新增**: 商业知识检索 LLM (含 web_search tool calling)

### Design
- 三阶段 LLM 管线彻底分离：商业检索(知识广度+搜索) → 分析Agent(推理+长篇写作) → 交叉验证(严格JSON+事实核查)
- 分析 Agent 的交叉验证靶子从"管线得分"改为"分析报告结论"——v0.26 已将管线 vs 财报洞察矛盾率降至40%，真正需要验证的是 LLM 分析 Agent 的推理偏差
- 商业检索前置到 Phase 4 之前，让 brief.md 携带完整商业知识，分析 Agent 无需自行搜索
- 降级链：无 API Key → Phase 3.5 跳过 → Phase 5a 降级 local_analysis_engine → Phase 5b 降级 _fallback_validate

### Files
- `src/llm/tools.py` — 新文件
- `src/llm/business_retrieval_agent.py` — 新文件
- `src/llm/client.py` — 修改（+chat_with_tools(), +三模型配置）
- `src/llm/analysis_agent.py` — 重构（输入 brief.md）
- `src/llm/cross_validation_agent.py` — 重构（验证分析报告）
- `src/reporter/brief_md_builder.py` — 修改（+Section 5, 重写 Section 4）
- `src/cli.py` — 重构（统一管线，移除分叉）
- `.env.example` — 修改（+TAVILY_API_KEY, +三模型 env var）
- `pyproject.toml`, `CHANGELOG.md`, `PROJECT_STATUS.md`, `README.md`, `TRACEABILITY.md`, `docs/plan.md`, `.codebuddy/memory/MEMORY.md`

---

## [v0.26] - 2026-06-03 — Bug修复：取数粒度 + 单位换算 + 送转股 + NaN防御

### Fixed
- **财报深度分析取数粒度Bug**: `_get_yearly()`/`_get_yearly_years()` 不区分季报/年报，Q1 营收与年报直接做CAGR导致-24.9%（应为+6.9%）。修复: 增加 `endswith("1231")` 年报过滤 + 升序 `tail(n)` 保证时序正确
- **DuPont/营运效率取数Bug**: `_analyze_roe_dupont()`/`_analyze_efficiency()` 按位置对齐 income 与 balance（无年报过滤），改为按 `end_date` 精确匹配
- **DisposableCash 列名Bug**: `st_borrow`/`tradable_fin_assets` 在 Tushare 中不存在 → DC=NaN。修复: `st_borr`/`trad_asset` + `_safe_val()` NaN防御
- **L5 合理市值显示Bug**: `l5_reasonable_mv` 为万元，但显示时除以 1e8（应为 1e4）→ 1.1万亿 显示为 1.1亿
- **L5 资产底价单位Bug**: `_eval_asset_floor()` 中 `net_liquid`(元) 与 `current_mv`(万元) 直接相除，比率差 10000x
- **L3 股本变动Bug**: `_eval_share_count_trend()` 将送转股（`stk_div`+`stk_bo_rate`）当作融资摊薄扣分

### Changed
- `_get_yearly()` 默认排序改为 `ascending=True`，`tail(n)` 取最新 n 年
- DisposableCash 所有字段统一使用 `_safe_val()` 防护 NaN（Pandas `or 0` 不可靠）

### Results
- 茅台交叉验证矛盾率: **4/7 (57%) → 2/5 (40%)**
- 财报数据全量修复: 营收CAGR -24.9%→6.9%, 经营CF/NI 10.84→0.75, 净负债率 27%→16.4%, 自由现金流 21亿→546亿
- DC 从 NaN → 1075亿, PR 从 NaN% → 4.33%

### Files
- `src/calculator/financial_deep_analysis.py` — 取数粒度修复
- `src/calculator/turtle_strategy/l5_calculator.py` — 资产底价单位修复
- `src/calculator/turtle_strategy/l3_calculator.py` — 股本变动修复
- `src/data_pool/schema/disposable_cash.py` — 列名修复 + NaN防御
- `src/reporter/brief_md_builder.py` — 合理市值显示修复
- `src/reporter/report_generator.py` — 合理市值显示修复

---

## [v0.25] - 2026-06-03 — 财报深度分析 + LLM 商业知识检索 + 三维交叉验证

### Added
- **财报深度分析引擎** (`financial_deep_analysis.py`): 7模块纯Python计算，从Tushare三大报表提取结构化洞察（收入利润趋势/利润率拆解/ROE杜邦/现金流质量/资产负债健康度/分红政策/营运效率），输出 `FinancialInsights` dataclass
- **LLM 商业知识检索** (集成到 `cross_validation_agent.py`): 合并检索+交叉验证为一步，LLM 基于训练数据回答5类商业问题（商业模式/管理层/行业地位/风险监管/分红回购），同时三维对比（管线得分 vs 财报洞察 vs LLM知识）

### Changed
- **交叉验证 Agent 重写**: System prompt 从二维对比（管线vs Web）升级为三维对比（管线 vs 财报洞察 vs LLM知识）
- **brief.md 重构**: Section 3 从「Web搜索商业分析」改为「财报深度分析洞察」+「交叉验证结果」
- **CLI 管线重排**: Phase 3→财报深度分析, Phase 4→LLM商业知识检索+交叉验证（合并）, Phase 5→brief.md, Phase 6→HTML报告
- `orchestrator.py`: 新增 `cache_financial_insights()` 方法
- `StockDataBundle`: `web_search_results` → `financial_insights`
- `report_generator.py`: `_build_cv_context` 接入 `FinancialInsights`
- `cross_validated_report.html`: 新增财报洞察7模块展示区

### Removed
- **DuckDuckGo Web 搜索** 全面删除：`web_searcher.py` 删除，所有引用清理（中文搜索质量差，LLM训练数据更可靠）
- `pyproject.toml`: 移除 `duckduckgo-search` 依赖

### Design
- 财报洞察 vs LLM知识彻底分离：前者纯Python确定性计算，后者LLM质性判断
- 商业知识检索+交叉验证合并为一次LLM调用，减少延迟
- 降级链：API LLM → Python规则引擎（财报洞察 vs 管线得分简单对比）

### Files
- `src/calculator/financial_deep_analysis.py` — 新文件 (~450行)
- `src/data_fetcher/web_searcher.py` — 删除
- `src/llm/cross_validation_agent.py` — 重写 (~350行)
- `src/reporter/brief_md_builder.py` — 重构（4块结构）
- `src/cli.py` — 改造（管线重排）
- `src/data_fetcher/orchestrator.py` — 改造（移除 run_web_search）
- `src/data_pool/bundle.py` — 改造（字段替换）
- `src/data_fetcher/__init__.py` — 改造（移除 DuckDuckGo 相关导出）
- `src/reporter/report_generator.py` — 改造（接入 FinancialInsights）
- `src/reporter/templates/cross_validated_report.html` — 改造（新增财报洞察区）
- `TRACEABILITY.md`, `CHANGELOG.md`, `PROJECT_STATUS.md`, `docs/plan.md`, `scripts/verify_traceability.py`, `.codebuddy/memory/MEMORY.md`, `pyproject.toml`, `README.md`

---

## [v0.24] - 2026-06-03 — Web 搜索 + brief.md 数据底稿 + LLM 交叉验证

### Added
- **Web 搜索器** (`web_searcher.py`): `SearchBackend` 抽象基类 + `DuckDuckGoBackend` 默认实现，5类广义商业研究（商业模式/管理层/行业地位/风险监管/分红回购），可插拔切换 Bing/SerpAPI
- **brief.md 数据底稿组装器** (`brief_md_builder.py`): 拼合 Tushare原始数据 + L2-L5管线得分 + Web搜索结果 → Markdown 字符串，作为 LLM 交叉验证的输入
- **LLM 交叉验证 Agent** (`cross_validation_agent.py`): 读 brief.md → 逐维对比 Web 搜索结果 vs L2-L5 得分 → 标注不一致 → 输出结构化结论 + 修正建议
- **含交叉验证结论的 HTML 报告** (`cross_validated_report.html`): 新模板，在现有报告基础上新增交叉验证结论展示区域
- **CLI** 新增 `--cross-validate` 参数，编排 Phase 3(Web搜索) → Phase 4(brief.md) → Phase 5(LLM交叉验证) → Phase 6(报告)

### Changed
- `orchestrator.py`: 新增 `_fetch_web_search()` 方法，在 Phase 2 打分后执行 Web 搜索
- `StockDataBundle`: 新增 `web_search_results: dict` 字段
- `__init__.py` (data_fetcher): 导出 WebSearcher
- `report_generator.py`: 新增 `generate_cross_validated()` / `save_cross_validated()` 方法

### Design
- Web 搜索不是逐维定向搜索，而是 5 类广义商业研究
- brief.md 是管线运行后的"数据档案"，三块合一，不是最终输出品
- LLM 自己读 brief.md 做逐维对比，不做预筛选/预匹配

### Files
- `src/data_fetcher/web_searcher.py` — 新文件 (~300行)
- `src/reporter/brief_md_builder.py` — 新文件 (~400行)
- `src/llm/cross_validation_agent.py` — 新文件 (~350行)
- `src/reporter/templates/cross_validated_report.html` — 新文件 (~500行)
- `src/data_fetcher/orchestrator.py` — 修改（新增 Web 搜索调用）
- `src/data_fetcher/__init__.py` — 修改（导出 WebSearcher）
- `src/cli.py` — 修改（新增 --cross-validate 参数）
- `src/reporter/report_generator.py` — 修改（新增交叉验证报告方法）
- `src/data_pool/bundle.py` — 修改（新增 web_search_results 字段）
- `TRACEABILITY.md`, `CHANGELOG.md`, `PROJECT_STATUS.md`, `docs/plan.md`, `scripts/verify_traceability.py`, `.codebuddy/memory/MEMORY.md`

---

## [v0.23] - 2026-06-03 — L3 十二维商业模式评估 + L5 估值安全边际重构 + 加法百分制

### Added
- **L3 十二维商业模式评估** (`l3_calculator.py`): ROE水平/稳定性, ROIC-ROE差距, 毛利率水平/稳定性(盈利能力5维) + CAPEX/经营CF, 总资产CAGR, 营收CAGR(成熟度3维) + 分红持续性, 股本变动(资本纪律2维) + 管理层稳定性, 盈利真实性(治理2维)
  - 每维0-2分, 满分24→映射到0-30分
  - 等级: 优(20-24)/良(14-19)/中(8-13)/差(0-7)
- **ROIC 计算**: NOPAT / Invested Capital, 用于检测高杠杆伪装高ROE

### Changed
- **评分公式**: `Final = (L2+L4+L5)×L3` → `Final = L3_30pt + L4_45pt + L5_25pt = 100pt`
- **L2 降级为纯门控**: 不再参与最终评分, 仅保留淘汰功能
- **L3 从乘法器变加法**: 旧 `×1.2/×1.0/×0.8/reject` → 新 `0-30 分加法`
- **L4 满分**: 40→45pt (内部缩放 45/40)
- **L5 重构为纯估值保护**: 去掉外推可行度6维+价值陷阱5项, 改为估值安全边际率(0-15)+下行缓冲(0-5)+仓位矩阵(0-5)
  - 折现率: 7% = max(无风险利率+2%, 5%) + 个股风险溢价2%
  - 合理市值 = 可分配现金 / 7%
  - 安全边际率 → 仓位映射: ≥30%→15%, 15-30%→10%, 0-15%→5%, <0%→0%
- **分池阈值**: 核心≥75, 观察50-74, 备选<50 (比旧55→50放宽)
- **YAML 配置**: `business_model_multiplier` → `business_model` (十二维), `margin_of_safety` 完全重写

### Removed
- `_estimate_l3()` 方法 (被 L3Calculator 替代)
- `BusinessModelMultiplier` Pydantic 模型
- L5 外推可行度 6 维评分函数
- L5 价值陷阱 5 项检查函数
- L5 3×3 仓位矩阵旧逻辑

### Files Changed
- `rules/turtle_constants.yaml` — 重写 business_model + margin_of_safety + scoring 章节
- `src/rules/schemas.py` — BusinessModelConfig + 新 MarginOfSafety + 更新 validators
- `src/calculator/turtle_strategy/l3_calculator.py` — 新文件 (~320行)
- `src/calculator/turtle_strategy/l5_calculator.py` — 完全重写
- `src/calculator/turtle_strategy/scoring.py` — 集成新 L3/L5 + 百分制缩放
- `src/reporter/report_generator.py` — 十二维展开 + L5 估值分解展示
- `CHANGELOG.md`, `PROJECT_STATUS.md`

---

## [v0.23] - 2026-06-03 (追加) — 简报功能：数据溯源 + 管线推导

### Added
- **简报 (Brief) 模块**: 在完整 HTML 报告之外新增轻量简报，包含：
  - **区域 A · 核心数据趋势**: 4 张表 — A1 三大报表合并视图(亿) / A2 财务指标(%) / A3 估值快照(最新交易日) / A4 分红记录(元/股)
  - **区域 B · 管线计算推导**: 5 张表 — B1 HardGate / B2 L2初筛 / B3 L3十二维 / B4 L4穿透回报率公式展开 / B5 L5安全边际
  - 所有简称统一中文，所有货币量统一为「亿元」
- **可配置单位转换层** (`unit_converter.py`): `DATA_SOURCE` 字典定义各字段源单位（三大报表=元, daily_basic=万元, fina_indicator=%, dividend=元/股），`to_yi()` 一键转亿元。切换港股/美股只需加配置，自检≤十万亿报警
- **简报组装器** (`brief_builder.py`): 从 `StockDataBundle` + `FinalScore` 提取所有原始值+中间计算值，组装 Jinja2 context
- **`--brief` CLI 参数**: `stock-analyze 600519.SH --brief` 生成 `brief_600519_SH.html`

### Files Changed
- `src/reporter/unit_converter.py` — 新文件 (~140行)
- `src/reporter/brief_builder.py` — 新文件 (~420行)
- `src/reporter/templates/rich_brief.html` — 新文件 (~260行)
- `src/reporter/report_generator.py` — 新增 `generate_brief()` / `save_brief()` 方法
- `src/cli.py` — 新增 `--brief` 参数
- `TRACEABILITY.md`, `CHANGELOG.md`, `PROJECT_STATUS.md`, `docs/plan.md`


## [v0.22] - 2026-06-02 — DC 扣除成长性投入 + PR 真实数学回报

### Changed
- **DC 公式扩展**: 新增扣除「并购子公司支付的现金(`c_pay_acq_subsidiary`)」和「参股净增额(`max(0, 年末长投 - 年初长投)`)」
  - 所有成长性投入(建厂+并购+参股)全部扣除，理财等可逆资金配置不被误扣
  - 公式: `op_cf - capEx - 并购子公司 - 参股净增 - finExpense + moneyCap - restricted - stBorr + tradAssets`
- **分配比率改为 mean(分红/净利润)**:
  - 分母从 DC 改为净利润，消除循环依赖(v0.21 的 adjusted_dc 加回修正不再需要)
  - 聚合从 `np.median` 改为 `np.mean`(算术平均，等权重)
  - 年份固定为近5年
- **PR 公式简化**:
  - 去除安全边际系数(一档 ×0.8 / 二档 ×0.7)
  - 去除红利税折扣(×0.9 → ×1.0)
  - `PR = (DC × 分配比率 + 回购注销) / 当前市值` — 直接反映数学真实回报
- **红利税备注**: 报告中添加黄框提示「持股<1月需缴10%红利税」

### Removed
- `_tax_cfg.dividend_withholding` 在 PR 公式中不再使用（设为 0）
- `_extrapolate_from_history` 中的 v0.21 adjusted_dc 加回逻辑（分红/净利润 无循环依赖，不再需要）


## [v0.21] - 2026-06-02 — 分配比率外推循环悖论修正

### Fixed
- **分配比率外推循环悖论**: DC 公式包含年末 money_cap，该值已被当年分红抽走。外推 `ratio = total_div / DC` 造成：分红越多 → 年末现金越少 → DC 越小 → ratio 虚高（早年可达 133%）
- 修正：`_extrapolate_from_history()` 中 `adjusted_dc = dc + total_div`（把分红加回年末现金），再用 `total_div / adjusted_dc` 算比率
- ratio 天然 ≤ 100%，消除循环悖论，无需另存年初 money_cap


## [v0.20] - 2026-06-02 — DC maintenance_capex 修正

### Fixed
- **DC 公式维护性 CAPEX 范围修正**: `c_pay_acq_const_fiolta`（购建固定资产、无形资产及其他长期资产支付的现金）替代 `stot_out_inv_act`（投资活动现金流出总计）
- 只扣维持性 CAPEX（建厂、买设备），不再扣所有投资流出（含短期理财、参股等金融投资）
- 参股/并购→长期股权投资→不被加回（永久扣掉）；短期理财→交易性金融资产→末尾加回（净效果为零）


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

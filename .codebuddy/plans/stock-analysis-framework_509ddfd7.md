---
name: stock-analysis-framework
overview: 在 D:\project\stock-analysis-framework\ 创建 Python 股票分析框架，集成龟龟投资策略框架（Factor 1A HardGate 否决制 + L2 多维初筛 + 乘法打分模型 + 双轨穿透回报率 + 公司分类注册表 + SOTP 双轨估值），通过 4 阶段递进实施。
todos:
  - id: phase1-scaffold
    content: 阶段一：创建项目骨架——pyproject.toml、Makefile、.pre-commit-config.yaml、.gitignore、.env.example、README.md、.codebuddyrules、.editorconfig、.vscode三件套、PROJECT_STATUS.md、ISSUES.md、CHANGELOG.md、notebooks/、全部src/和tests/子包目录结构，及新增rules/下turtle相关YAML配置文件
    status: pending
  - id: phase1-utils
    content: 阶段一：搭建基础设施层——src/utils/exceptions.py（5个自定义异常）、logger.py（loguru封装）、retry.py（tenacity封装）、config.py（pydantic-settings含TUSHARE_TOKEN）、constants.py（汇率/税率/无风险利率/门坎等全局参数）、validators.py，编写对应单元测试
    status: pending
    dependencies:
      - phase1-scaffold
  - id: phase1-data-pool-schema
    content: 阶段一：实现数据池核心——src/data_pool/schema.py（19个Pydantic模型+StockDataPackage聚合体）、validator.py（DataValidator完整度评分/审计意见检查/商誉预警）、storage.py（JSON+Parquet双格式存储）、transformer.py（DataFrame至Pydantic转换），编写完整单元测试
    status: pending
    dependencies:
      - phase1-utils
  - id: phase2-hardgate
    content: 阶段二：实现HardGate否决器——src/screener/hard_gate.py（6项一票否决：审计异常/频繁换所/ST标记/上市未满5年/短期暴涨跌/人工黑名单，仅用3轻量接口，不合规直接标记排除不取全量），配置文件rules/hard_gate_rules.yaml，编写单元测试
    status: pending
    dependencies:
      - phase1-data-pool-schema
  - id: phase2-l2-classifier
    content: 阶段二：实现L2初筛与公司分类——src/screener/l2_screener.py（fina_indicator批量拉取，8指标+3硬门控+加分项，20分制，12分以上进候选池）、src/screener/classifier.py（5类自动分类：STANDARD/HOLDING/CYCLICAL/FINANCIAL/GROWTH_NO_DIV）、src/screener/stock_pool.py（核心/观察/备选股票池管理），配置rules/l2_screener_rules.yaml，编写单元测试
    status: pending
    dependencies:
      - phase2-hardgate
  - id: phase2-data-fetcher
    content: 阶段二：实现Tushare数据获取——src/data_fetcher/（base.py抽象基类、tushare_financial.py 8财报、tushare_market.py 6行情、tushare_holder.py 8股东、web_search.py、orchestrator.py并行编排器+tenacity重试+Tushare频率控制）
    status: pending
    dependencies:
      - phase1-data-pool-schema
  - id: phase2-pool-transformer
    content: 阶段二：实现数据池转换——src/data_pool/transformer.py（Tushare dict/DataFrame至Pydantic转换，双轨：核心字段至Schema+全量至RawTushareData）、pool_manager.py（fetch至transform至validate至store全流程）
    status: pending
    dependencies:
      - phase2-data-fetcher
      - phase1-data-pool-schema
  - id: phase2-calculator-registry
    content: 阶段二：实现策略注册表与龟龟指标——src/calculator/registry.py（StrategyRegistry按分类匹配管线，策略注册/分类/分发）、src/calculator/turtle_strategy/（owners_earnings.py粗算穿透回报率含维持CAPEX系数表、penet_return.py双轨制含HH偏差扣分、cash_recon.py真实可支配现金重建极端保守、sotp_adjust.py控股公司双口径调整、margin_safety.py安全边际/仓位矩阵/价值陷阱5项排查、constants_turtle.py龟龟专用常数），配置rules/turtle_constants.yaml，编写单元测试
    status: pending
    dependencies:
      - phase1-data-pool-schema
  - id: phase2-financial-ratios
    content: 阶段二：实现通用比率与打分——src/calculator/financial_ratios.py（杜邦分解/现金流质量/CAGR/估值历史分位）、src/calculator/scoring.py（乘法打分：(L2+L4+L5)×L3乘数，≥75核心池/55-74观察池/
    status: pending
    dependencies:
      - phase2-calculator-registry
---

## 产品概述

在 `D:\project\stock-analysis-framework\` 创建 Python 股票分析框架，融合 **龟龟投资策略框架（Turtle Strategy v0.13，UP主 Ternis）** 完整方法论——从 HardGate 一票否决、L2 分层初筛、公司分类、双轨穿透回报率计算到乘数打分模型，实现从选股到报告生成的完整分析管线。系统采用确定性计算与 LLM 智能分析分离的架构，以 **Tushare（2000积分会员）** 为主要数据源，覆盖 **22 个接口**（8 财报 + 6 行情 + 8 股东治理）+ 行业数据，辅以 Web 搜索，通过 2 个 LLM Agent（分析+验证）配合 Jinja2 模板渲染输出 HTML+MD 格式的股票分析报告。

## 核心功能

### 选股器：HardGate 否决 + L2 分层初筛 + 公司分类 + 股票池

- **HardGate（龟龟因子一A）**：6项一票否决，仅用3个轻量Tushare接口（fina_audit、stock_basic、daily_basic），任何一项触发直接丢弃，不取全量数据，节省约90% API调用和存储。审计意见异常、频繁更换审计师、看不懂（人工黑名单）、上市未满5年、ST/*ST、短期暴涨暴跌（近60日 >150% 或 <-60%）
- **L2 初筛（20分）**：HardGate通过后批量拉取 fina_indicator（1次API调用），得分≥12进入候选池拉全量22接口数据。维度：财务质量9pt（ROE 3+毛利率 2+资产负债率 2+经营现金流/净利润 2）+ 估值合理性6pt（PE 3+PB 2+PS 1）+ 流动性健康3pt（股息率 2+日均换手率 1）+ 加分项2pt（沪深港通+1，上市>10年+1）。硬门控：ROE<5%、PE<0、股息率=0直接淘汰。8~11分进观察池（低优先级），<8分淘汰
- **公司分类**：STANDARD_CONSUMER（消费/医药/公用）、HOLDING_COMPANY（控股型）、CYCLICAL（强周期）、FINANCIAL（金融类）、GROWTH_NO_DIVIDEND（成长不分配，仅观察池）。自动分类后匹配不同策略管线

### 数据获取

Tushare 22 接口（8财报+6行情+8股东治理）+ 行业数据 + Web搜索。多 Adapter 设计（TushareFinancialFetcher / TushareMarketFetcher / TushareHolderFetcher / WebSearchFetcher），支持编排器并行调用与 tenacity 错误重试

### 数据池

19 个 Pydantic v2 模型（三表明细、财务指标、估值行情、股东、高管、分红、审计意见、资金流向、限售解禁、股份回购、行业指数等），双轨 Schema（核心字段显式定义 + RawTushareData 全量原始字段保留）。自动数据质量验证，数据快照持久化

### 计算引擎：龟龟策略 + 通用比率 + 策略注册表

- **策略注册表（StrategyRegistry）**：按公司分类匹配估值管线，可扩展多估值锚定
- **龟龟策略指标**：Owners' Earnings（维持性CAPEX系数表）、粗算/精算双轨穿透回报率（HH偏差扣分）、真实可支配现金重建（极端保守）、经营弹性系数L、安全边际+仓位矩阵（外推可行度×价值陷阱风险3×3交叉）、价值陷阱5项排查
- **通用财务比率**：杜邦分解、现金流质量、CAGR、估值分位等

### 乘法打分模型

Final Score = (L2初筛 20pt + L4穿透回报率 40pt + L5安全边际 25pt) × L3商业模式乘数(1.2/1.0/0.8)。L3为"差"则截断不进后续。L4 双轨制：粗算达标直接得分(起点20)；粗算边缘进精算可翻盘但起点压低(15)；HH偏差>2%扣分+标记。≥75核心池，55~74观察池，<55备选池

### SOTP 冲突双轨解决方案

控股型公司（HOLDING_COMPANY）双口径穿透回报率：口径A=母公司报表可支配现金÷市值（保守），口径B=合并报表可支配现金×分红回流率÷市值（调整）。|A-B|>2pp时Agent综合判断控股折价是否已定价

### LLM 智能层 + 报告生成

分析 Agent 一次性完成定性+定量+风险分析（因子一B 9模块定性），验证 Agent 做交叉验证（MD&A兑现率）与数据引用检查。SharedContext 三层（Immutable→Enriched→Opinion），Jinja2 模板渲染 HTML+MD 报告。

## 龟龟策略集成设计

### 四因子到框架的映射

| 龟龟因子 | 框架映射 | 模块 |
| --- | --- | --- |
| 因子一A（5分钟快筛） | HardGate 一票否决 | screener/hard_gate.py |
| 模块零（数据预提取） | Fetcher + Clean + ImmutableLayer | data_fetcher/ + data_pool/ |
| 因子一B（9模块定性） | LLM 分析Agent + OpinionLayer | agents/ + rules/ |
| 因子二（粗算穿透回报率） | Engine Owners' Earnings | calculator/turtle_strategy/ |
| 因子三（精算真实可支配现金） | Engine 极端保守扣除 | calculator/turtle_strategy/ |
| 因子四（估值+仓位） | Engine 安全边际+仓位矩阵 | calculator/turtle_strategy/ |

### HardGate 否决项设计

6项检查仅需3个轻量接口，不通过则直接标记为"排除"，不进入后续拉全量数据流程。接口1：fina_audit（审计意见异常+频繁更换审计师），接口2：stock_basic（ST标记+上市年限），接口3：daily_basic（短期暴涨暴跌），另1项"看不懂"通过人工黑名单配置文件实现零API开销。

### L2 初筛打分表

| 维度 | 指标 | 条件 | 得分 |
| --- | --- | --- | --- |
| 财务质量(9) | ROE | ≥15% / 10-15% / 5-10% / <5%或负 | 3/2/1/0 |
|  | 毛利率 | ≥40% / 20-40% / <20% | 2/1/0 |
|  | 资产负债率 | 20-50% / <20%或50-70% / >70% | 2/1/0 |
|  | 经营现金流/净利润 | ≥0.8 / 0.5-0.8 / <0.5 | 2/1/0 |
| 估值(6) | PE(TTM) | 10-20 / 5-10或20-30 / 0-5或30-50 / <0或>50 | 3/2/1/0 |
|  | PB | 1-3 / 0.5-1或3-5 / <0.5或>5 | 2/1/0 |
|  | PS | <5 / ≥5 | 1/0 |
| 流动性(3) | 股息率 | ≥3% / 1.5-3% / <1.5%或0 | 2/1/0 |
|  | 日均换手率 | 0.3-3% / <0.1%或>10% | 1/0 |
| 加分(2) | 沪深港通 | 是 | +1 |
|  | 上市>10年 | 是 | +1 |

硬门控（不计分，直接淘汰）：ROE<5%、PE<0（亏损）、股息率=0。L2≥12→候选池拉全量，8-11→观察池，<8→淘汰。

### 公司分类与策略注册表

5类公司自动分类后匹配不同估值管线。分类依据：1）行业属性（金融/周期/消费等）2）控股结构（top10_holders中是否含上市公司股权，投资收益/净利润>30%）3）分红特征（有无稳定分红）。STANDARD_CONSUMER走标准龟龟合并报表路径，HOLDING_COMPANY走SOTP双轨路径（口径A母公司+口径B分红回流调整），CYCLICAL走周期均值化修正路径（门坎±1~2pp调整），FINANCIAL走PB-ROE框架（非龟龟原生），GROWTH_NO_DIVIDEND仅观察池。

### 双轨穿透回报率

粗算（因子二）：Owners' Earnings/市值，10分钟内完成，门坎=MAX(绝对底线, 无风险利率+风险补偿)，A股3.5%/港股5%。粗算≥门坎→直接进入L4计分(起点20)；粗算<门坎×0.5→硬淘汰；门坎×0.5≤粗算<门坎→进入精算。精算（因子三）：真实可支配现金（极端保守全扣资本开支+对外投资+受限现金）/市值，可翻盘但L4起点压低至15。HH=|粗算-精算|>2%→扣2-5分+profit_cash_gap标记。L4满分40。

### 乘法打分公式

Final Score = (L2 20pt + L4 40pt + L5 25pt) × L3乘数。L3商业模式乘数由分析Agent根据因子一B 9模块定性判断：优=1.2、良=1.0、中=0.8、差=截断不进。L5安全边际=MAX(0, 精算穿透回报率-门坎)，与外推可行度（高/中/低）和价值陷阱风险（低/中/高，≥2项高风险需穿透回报率≥门坎×1.5方可进入）三维交叉决定。≥75核心池，55-74观察池，<55备选池。

## 实施策略（四阶段递进）

- **阶段一（地基）**：项目骨架+基础设施层+19 Pydantic Schema+数据校验存储+3规则YAML
- **阶段二（确定性管线）**：HardGate+L2初筛分类+Tushare 22接口+数据池转换+策略注册表+龟龟指标+通用比率+打分+报告渲染+集成测试
- **阶段三（LLM智能层）**：Rules加载注入+LLM基础设施+SharedContext+分析Agent+验证Agent+Agent管线测试
- **阶段四（质量加固）**：端到端测试+CI配置+项目文档+examples

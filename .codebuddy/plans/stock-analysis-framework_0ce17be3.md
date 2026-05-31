---
name: stock-analysis-framework
overview: 在 D:\project\stock-analysis-framework\ 创建 Python 股票分析框架，Tushare（2000积分）22接口为主要数据源，19个Pydantic Schema模型，SharedContext三层上下文管理，JSON+Parquet存储，实现选股→数据池→计算引擎→LLM分析→报告生成完整管线。
todos:
  - id: phase1-scaffold
    content: 阶段一：创建项目骨架——pyproject.toml（含ruff/loguru/tenacity/pydantic-settings/tushare/pyarrow/jupyter/matplotlib/plotly依赖及工具配置）、Makefile、.pre-commit-config.yaml、.gitignore、.env.example、README.md、.codebuddyrules、.editorconfig、.vscode三件套、PROJECT_STATUS.md、ISSUES.md、CHANGELOG.md、notebooks/目录、全部src/和tests/子包目录结构
    status: pending
  - id: phase1-utils
    content: 阶段一：搭建基础设施层——src/utils/exceptions.py（5个自定义异常）、src/utils/logger.py（loguru封装）、src/utils/retry.py（tenacity封装）、src/utils/config.py（pydantic-settings含TUSHARE_TOKEN）、src/utils/constants.py（汇率/税率/无风险利率/数据年限等全局参数）、src/utils/validators.py，编写对应单元测试
    status: pending
    dependencies:
      - phase1-scaffold
  - id: phase1-data-pool-schema
    content: 阶段一：实现数据池核心——src/data_pool/schema.py（19个Pydantic模型：BalanceSheetLine/IncomeStatementLine/CashFlowLine/FinancialIndicator/DailyBasic/DailyBar/PerformanceForecast/PerformanceExpress/StockBasicInfo/AuditOpinion/DividendRecord/MoneyFlow/TopHolder/HolderNumber/InsiderTrade/ManagerInfo/ManagerReward/ShareFloat/RepurchaseRecord/IndustryIndex/RawTushareData/StockDataPackage聚合体，含model_validator恒等式检查）、src/data_pool/validator.py（DataValidator：完整度评分/审计意见检查/商誉预警）、src/data_pool/storage.py（JSON+Parquet双格式存储，每条股票一个目录），编写完整单元测试
    status: pending
    dependencies:
      - phase1-utils
  - id: phase2-screener
    content: 阶段二：实现选股器——src/screener/（base.py抽象基类ScreenFilter、initial_screen.py初筛、fine_screen.py细筛、stock_pool.py股票池管理），支持预设选股条件加载与自定义
    status: pending
    dependencies:
      - phase1-data-pool-schema
  - id: phase2-data-fetcher
    content: 阶段二：实现Tushare数据获取——src/data_fetcher/（base.py BaseDataSource抽象基类、tushare_financial.py对接8财报接口、tushare_market.py对接6行情接口、tushare_holder.py对接8股东接口、web_search.py Web搜索、orchestrator.py并行编排器），所有接口使用tenacity重试+Tushare频率控制
    status: pending
    dependencies:
      - phase1-data-pool-schema
  - id: phase2-pool-transformer
    content: 阶段二：实现数据池转换与管理——src/data_pool/transformer.py（Tushare dict/DataFrame→Pydantic转换，自动类型校验与单位换算，双轨写入：核心字段→Schema + 全量→RawTushareData）、src/data_pool/pool_manager.py（PoolManager：fetch→transform→validate→store全流程封装）
    status: pending
    dependencies:
      - phase2-data-fetcher
      - phase1-data-pool-schema
  - id: phase2-calculator
    content: 阶段二：实现计算引擎——src/calculator/（base.py计算器抽象基类、turtle_metrics.py龟龟策略指标（穿透回报率/护城河评分/增长稳定性/估值安全边际）、financial_ratios.py通用财务比率（ROE杜邦分解/现金流含金量/CAGR/PE-PB历史分位等）、registry.py计算器注册表），从Schema取数、从Constants取参数
    status: pending
    dependencies:
      - phase1-data-pool-schema
  - id: phase2-reporter
    content: 阶段二：实现报告渲染——src/reporter/renderer.py（Jinja2渲染引擎）、src/reporter/templates/report_template.md + report_template.html（含CSS样式与plotly图表嵌入），ReportData Pydantic模型定义
    status: pending
    dependencies:
      - phase2-calculator
  - id: phase2-integration-test
    content: 阶段二：编写确定性管线集成测试——tests/integration/test_data_flow.py（选股→Tushare数据获取→数据池→计算→报告全流程），使用Mock数据源验证端到端管线可运行
    status: pending
    dependencies:
      - phase2-pool-transformer
      - phase2-calculator
      - phase2-reporter
  - id: phase3-rules-config
    content: 阶段三：创建Rules配置层——rules/目录下constraint_rules.yaml（LLM输出约束）、llm_prompt_rules.md（系统提示词规则）、module_contract.yaml（模块开发契约）、agent_pipeline.yaml（Agent调度管线定义）、analysis_dimensions.yaml（分析维度定义）
    status: pending
    dependencies:
      - phase1-scaffold
  - id: phase3-rules-loader
    content: 阶段三：实现规则执行层——src/rules/loader.py（从YAML/MD加载规则并解析为Pydantic模型）、src/rules/validator.py（规则格式校验与引用完整性检查）、src/rules/injector.py（将约束规则注入LLM System Prompt）
    status: pending
    dependencies:
      - phase3-rules-config
  - id: phase3-llm-infra
    content: 阶段三：实现LLM基础设施——src/llm/provider.py（LLMProvider抽象+OpenAI/Claude/Local实现）、src/llm/manager.py（LLMManager统一调用入口+路由）、src/llm/schema.py（LLMAnalysisOutput/QualitativeAnalysis/QuantitativeAnalysis/RiskAssessment Pydantic输出模型）、src/llm/validator.py（LLMOutputValidator输出校验与Schema约束）、src/llm/prompt_builder.py（PromptBuilder从SharedContext三层编译LLM结构化输入）、src/llm/cache.py（LLMCache响应缓存）
    status: pending
    dependencies:
      - phase3-rules-loader
  - id: phase3-agents-context
    content: 阶段三：实现多Agent上下文系统——src/agents/context.py（SharedContext三层：ImmutableLayer frozen只读/EnrichedLayer计算产出可扩展/OpinionLayer语义层可追加）、src/agents/context_builder.py（从StockDataPackage+Engine+WebSearch组装SharedContext）、src/agents/base.py（BaseAgent抽象基类）、src/agents/coordinator.py（按agent_pipeline.yaml编排Agent执行）、src/agents/checkpoint.py（CheckpointManager保存/加载/恢复SharedContext）
    status: pending
    dependencies:
      - phase3-llm-infra
  - id: phase3-analysis-agent
    content: 阶段三：实现分析Agent——src/agents/agents/analysis_agent.py（读取SharedContext不可变层+增强层，调用LLM完成定性+定量+风险分析，输出LLMAnalysisOutput，意见写入OpinionLayer）和src/agents/prompts/analysis_agent_prompt.md分析Agent提示词模板
    status: pending
    dependencies:
      - phase3-agents-context
  - id: phase3-validate-agent
    content: 阶段三：实现验证Agent——src/agents/agents/validate_agent.py（交叉验证分析Agent结论，检查数据引用准确性，标注置信度，写入OpinionLayer.verification_notes）和src/agents/prompts/validate_agent_prompt.md验证Agent提示词模板
    status: pending
    dependencies:
      - phase3-analysis-agent
  - id: phase3-agent-pipeline-test
    content: 阶段三：编写Agent管线集成测试——tests/integration/test_agent_pipeline.py（Mock LLM响应，验证分析Agent→验证Agent→报告渲染全流程正确对接）
    status: pending
    dependencies:
      - phase3-validate-agent
  - id: phase4-full-test
    content: 阶段四：编写端到端功能测试——tests/functional/test_e2e_workflow.py（输入股票代码→Tushare真实接口→完整HTML+MD报告）、tests/functional/test_report_output.py（报告格式校验：必含章节、数据准确性、LLM约束合规）
    status: pending
    dependencies:
      - phase3-agent-pipeline-test
      - phase2-integration-test
  - id: phase4-ci-docs
    content: 阶段四：配置CI与补全文档——.github/workflows/ci.yaml（lint→typecheck→test→coverage流水线）、docs/ARCHITECTURE.md、docs/DATA_SCHEMA.md（19模型字段清单）、docs/API_CONTRACT.md、docs/TESTING_GUIDE.md、examples/quick_start.py示例代码、补全所有模块__init__.py
    status: pending
    dependencies:
      - phase4-full-test
---

## 产品概述

在 `D:\project\stock-analysis-framework\` 创建 Python 股票分析框架，实现从选股到报告生成的完整分析管线。系统采用确定性计算与 LLM 智能分析分离的架构，以 **Tushare（2000积分会员）** 为主要数据源，覆盖 **22 个接口**（8 财报 + 6 行情 + 8 股东治理）+ 行业数据，辅以 Web 搜索，通过 2 个 LLM Agent（分析+验证）配合 Jinja2 模板渲染输出 HTML+MD 格式的股票分析报告。

## 核心功能

- **选股器**：初筛（市值/行业/PE粗条件）+ 细筛（多维度精细条件）+ 股票池管理
- **数据获取**：Tushare 22 接口（8财报+6行情+8股东治理）+ 行业数据 + Web搜索。多 Adapter 设计（TushareFinancialFetcher / TushareMarketFetcher / TushareHolderFetcher / WebSearchFetcher），支持编排器并行调用与 tenacity 错误重试
- **数据池**：19 个 Pydantic v2 模型（三表明细、财务指标、估值行情、股东、高管、分红、审计意见、资金流向、限售解禁、股份回购、行业指数等），双轨 Schema（核心字段显式定义 + RawTushareData 全量原始字段保留）。自动数据质量验证（资产负债恒等式、审计意见检查、商誉风险预警、完整度评分），数据快照持久化
- **数据清洗分层**：Fetcher 层做内容级清洗（去重/补缺/口径对齐），Schema 层做门禁级清洗（类型转换/范围校验/恒等式自检），Constants 层管理汇率/税率/全局参数
- **存储策略**：每条股票一个目录 `data_snapshots/{date}/{ts_code}/`，结构化数据 → JSON（package.json），大时间序列 → Parquet（压缩比 ~10:1）
- **计算引擎**：龟龟策略指标（穿透回报率等）+ 通用财务比率（杜邦分解、现金流质量、CAGR、估值分位等），可扩展注册表模式，从 Schema 取数、从 Constants 取参数
- **报告生成**：Jinja2 模板渲染 HTML+MD，LLM 输出结构化 JSON 作为报告数据源之一
- **LLM 智能层**：分析 Agent 一次性完成定性+定量+风险分析，验证 Agent 做交叉验证与数据引用检查
- **SharedContext 三层**：ImmutableLayer（frozen 原始数据只读）→ EnrichedLayer（Engine 计算产出可扩展）→ OpinionLayer（WebSearch + Agent 笔记可追加），PromptBuilder 从 SharedContext 编译 LLM 结构化输入
- **基础设施**：结构化日志（loguru）、错误重试（tenacity）、Checkpoint 断点恢复、自定义异常体系

## 技术栈

### 核心依赖

| 类别 | 库 | 用途 |
| --- | --- | --- |
| 语言 | Python 3.9+ | 运行环境 |
| 包管理 | Poetry | 依赖管理与虚拟环境 |
| 数据模型 | Pydantic v2 | 数据池 19 个 Schema + LLM 输出 Schema + SharedContext |
| 数据处理 | pandas, numpy | 财务报表数据处理与指标计算 |
| 模板引擎 | Jinja2 | HTML/MD 报告渲染 |
| 配置 | PyYAML, python-dotenv, pydantic-settings | 规则加载 + 环境变量 + 应用配置 |
| 日志 | loguru | 结构化 JSON 日志 |
| 重试 | tenacity | 数据获取与 LLM 调用重试 |
| 可视化 | matplotlib, plotly | 图表生成（Jupyter探索+HTML报告嵌入） |
| LLM | openai, anthropic | 多 Provider 适配 |
| 数据源 | tushare | A股财务/行情/股东数据（2000积分） |
| 存储 | pyarrow | Parquet 列式存储，大时间序列高性能读写 |

### 开发依赖

| 类别 | 库 | 说明 |
| --- | --- | --- |
| 测试 | pytest, pytest-cov | 单元/集成/功能测试 + 覆盖率 |
| 代码质量 | ruff | 统一替代 black + isort + flake8（Rust实现，极速） |
| 类型检查 | mypy | strict 模式，100% 类型注解覆盖 |
| 提交门禁 | pre-commit | 提交前自动检查 |
| 探索 | jupyter, ipykernel | 数据探索与指标验算 |
| Excel | openpyxl | 可选，报表导出 |

## 实施策略

### 四阶段递进原则

- 每个阶段产出可测试、可运行的最小单元
- 先确定性层（Python），后智能层（LLM）
- 核心数据池最先完成，作为所有下游模块的数据契约
- 每完成一个模块立即编写对应测试

### 阶段一：地基（项目骨架 + IDE配置 + 工具层 + 数据池核心）

搭建项目脚手架，配置 IDE 工具链和工程约定文件，完成基础设施层（日志/重试/配置/异常体系/常量）和 19 个 Pydantic Schema 模型定义、数据验证器、JSON + Parquet 双格式存储层。

### 阶段二：确定性管线（端到端可跑）

完成 Tushare 多 Adapter 数据获取器（22接口+行业）、DataFrame→Schema 转换器、选股器、计算引擎、报告渲染。此时整个管线可跑通（不含LLM），输出基础版股票分析报告。

### 阶段三：LLM 智能层（分析能力注入）

创建 Rules 配置层（YAML/MD）、规则执行层（loader/validator/injector）、LLM 基础设施（Provider/Manager/PromptBuilder/Cache）、Agent 上下文系统（SharedContext 三层/Coordinator/Checkpoint）、2 个 Agent 实现及提示词模板。PromptBuilder 从 SharedContext 编译完整分析上下文喂入 LLM。

### 阶段四：质量加固

编写端到端功能测试、CI 配置（GitHub Actions）、项目文档（架构/数据Schema/API契约/测试指南）、示例代码、补全所有模块 __init__.py。

## 数据架构

### 数据池 19 个 Pydantic 模型

**已有模型（9个，字段已增强）**：

- `BalanceSheetLine` — 资产负债表（12字段：总资产/负债/权益/流动资产/商誉/长短借款等）
- `IncomeStatementLine` — 利润表（含财务费用/投资收益/毛利）
- `CashFlowLine` — 现金流量表（含资本支出/股利支付/折旧摊销）
- `FinancialIndicator` — 财务指标（ROE/ROA/毛利率/周转率/现金流质量等，来自 `fina_indicator` 的70+字段）
- `DailyBasic` — 每日估值（PE/PB/PS/市值/换手率/量比/股息率）
- `DailyBar` — 日/周/月K线（OHLCV + adj_factor 复权因子）
- `PerformanceForecast` — 业绩预告
- `PerformanceExpress` — 业绩快报
- `StockBasicInfo` — 公司基本信息（行业/板块/上市日期/沪深港通标的）

**新增模型（10个）**：

- `AuditOpinion` — 审计意见（`fina_audit`）
- `DividendRecord` — 分红送转（`dividend`）
- `MoneyFlow` — 资金流向（`moneyflow`）
- `TopHolder` — 前十大股东（复用给 `top10_holders` + `top10_floatholders`）
- `HolderNumber` — 股东人数（`stk_holdernumber`）
- `InsiderTrade` — 高管增减持（`stk_holdertrade`）
- `ManagerInfo` — 管理层信息（`stk_managers`）
- `ManagerReward` — 管理层薪酬（`stk_rewards`）
- `ShareFloat` — 限售解禁（`share_float`）
- `RepurchaseRecord` — 股份回购（`repurchase`）
- `IndustryIndex` — 行业指数（`ths_index` / `ths_daily`）
- `RawTushareData` — Tushare 原始全量字段保留

### SharedContext 三层结构

- **ImmutableLayer**: frozen 只读，来自 StockDataPackage
- **EnrichedLayer**: Engine 计算产出（策略得分/CAGR/估值分位）
- **OpinionLayer**: WebSearch + Agent 笔记/风险标记
- PromptBuilder 从三层编译 LLM 结构化输入

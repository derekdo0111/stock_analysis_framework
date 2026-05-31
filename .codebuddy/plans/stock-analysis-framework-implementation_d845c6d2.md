---
name: stock-analysis-framework-implementation
overview: 在 D:\project\stock-analysis-framework\ 创建Python股票分析框架，分4阶段递进开发。本次更新整合了工程开发约定、IDE工具链、项目管理体系、依赖库优化等前期讨论的所有成果。
todos:
  - id: phase1-scaffold
    content: 阶段一：创建项目骨架——pyproject.toml（含ruff/loguru/tenacity/pydantic-settings/jupyter/matplotlib/plotly依赖及工具配置）、Makefile、.pre-commit-config.yaml、.gitignore、.env.example、README.md、CONTRIBUTING.md、.codebuddyrules、.editorconfig、.vscode/extensions.json、.vscode/settings.json、.vscode/launch.json、PROJECT_STATUS.md、ISSUES.md、CHANGELOG.md、notebooks/目录、全部src/和tests/子包目录结构
    status: pending
  - id: phase1-utils
    content: 阶段一：搭建基础设施层——src/utils/exceptions.py（自定义异常体系）、src/utils/logger.py（loguru轻量封装）、src/utils/retry.py（tenacity轻量封装）、src/utils/config.py（pydantic-settings配置管理）、src/utils/constants.py、src/utils/validators.py，编写对应单元测试
    status: pending
    dependencies:
      - phase1-scaffold
  - id: phase1-data-pool-schema
    content: 阶段一：实现数据池核心——src/data_pool/schema.py（Pydantic模型：BalanceSheet/IncomeStatement/CashFlow/StockDataPackage，含model_validator资产负债恒等式检查）、src/data_pool/validator.py（DataValidator：完整度评分、公式校验）、src/data_pool/storage.py（JSON持久化存储），编写完整单元测试
    status: pending
    dependencies:
      - phase1-utils
  - id: phase2-screener
    content: 阶段二：实现选股器——src/screener/（base.py抽象基类ScreenFilter、initial_screen.py初筛、fine_screen.py细筛、stock_pool.py股票池管理），支持预设选股条件加载与自定义
    status: pending
    dependencies:
      - phase1-data-pool-schema
  - id: phase2-data-fetcher
    content: 阶段二：实现数据获取——src/data_fetcher/（base.py DataSource抽象基类、statements.py三大报表、notes.py附注、market_data.py行情、web_search.py Web搜索、orchestrator.py并行编排器），所有外部调用使用tenacity重试
    status: pending
    dependencies:
      - phase1-data-pool-schema
  - id: phase2-pool-transformer
    content: 阶段二：实现数据池转换与管理——src/data_pool/transformer.py（DataFrame/dict→Pydantic转换，自动类型校验与单位换算）、src/data_pool/pool_manager.py（PoolManager：fetch→transform→validate→store全流程封装）
    status: pending
    dependencies:
      - phase2-data-fetcher
      - phase1-data-pool-schema
  - id: phase2-calculator
    content: 阶段二：实现计算引擎——src/calculator/（base.py计算器抽象基类、turtle_metrics.py龟龟策略指标（穿透回报率/护城河评分/增长稳定性/估值安全边际）、financial_ratios.py通用财务比率（ROE/ROA/毛利率/负债率等）、registry.py计算器注册表）
    status: pending
    dependencies:
      - phase1-data-pool-schema
  - id: phase2-reporter
    content: 阶段二：实现报告渲染——src/reporter/renderer.py（Jinja2渲染引擎）、src/reporter/templates/report_template.md + report_template.html（含CSS样式与plotly图表嵌入），ReportData Pydantic模型定义
    status: pending
    dependencies:
      - phase2-calculator
  - id: phase2-integration-test
    content: 阶段二：编写确定性管线集成测试——tests/integration/test_data_flow.py（选股→数据获取→数据池→计算→报告全流程），使用Mock数据源验证端到端管线可运行
    status: pending
    dependencies:
      - phase2-pool-transformer
      - phase2-calculator
      - phase2-reporter
  - id: phase3-rules-config
    content: 阶段三：创建Rules配置层——rules/目录下constraint_rules.yaml（LLM输出约束）、llm_prompt_rules.md（系统提示词规则）、module_contract.yaml（模块开发契约）、agent_pipeline.yaml（Agent调度管线定义）、analysis_dimensions.yaml（分析维度定义）、git_rules.yaml（Git提交规范）
    status: pending
    dependencies:
      - phase1-scaffold
  - id: phase3-rules-loader
    content: 阶段三：实现规则执行层——src/rules/loader.py（从YAML/MD加载规则并解析为Pydantic模型）、src/rules/validator.py（规则格式校验与引用完整性检查）、src/rules/injector.py（将约束规则注入LLM System Prompt）
    status: pending
    dependencies:
      - phase3-rules-config
  - id: phase3-llm-infra
    content: 阶段三：实现LLM基础设施——src/llm/provider.py（LLMProvider抽象+OpenAI/Claude/Local实现）、src/llm/manager.py（LLMManager统一调用入口+路由）、src/llm/schema.py（LLMAnalysisOutput/QualitativeAnalysis/QuantitativeAnalysis/RiskAssessment Pydantic输出模型）、src/llm/validator.py（LLMOutputValidator输出校验）、src/llm/prompt_builder.py（PromptBuilder组合数据+规则+模板）、src/llm/cache.py（LLMCache响应缓存）
    status: pending
    dependencies:
      - phase3-rules-loader
  - id: phase3-agents-context
    content: 阶段三：实现多Agent上下文系统——src/agents/base.py（BaseAgent抽象基类）、src/agents/context.py（SharedContext三层隔离：ImmutableLayer/EnrichedLayer/OpinionLayer）、src/agents/coordinator.py（Coordinator按agent_pipeline.yaml编排Agent执行）、src/agents/checkpoint.py（CheckpointManager保存/加载/恢复）
    status: pending
    dependencies:
      - phase3-llm-infra
  - id: phase3-analysis-agent
    content: 阶段三：实现分析Agent——src/agents/agents/analysis_agent.py（读取SharedContext不可变层，调用LLM完成定性+定量+风险分析，输出LLMAnalysisOutput写入增强层）和src/agents/prompts/analysis_agent_prompt.md分析Agent提示词模板
    status: pending
    dependencies:
      - phase3-agents-context
  - id: phase3-validate-agent
    content: 阶段三：实现验证Agent——src/agents/agents/validate_agent.py（交叉验证分析Agent结论，检查数据引用准确性，标注置信度）和src/agents/prompts/validate_agent_prompt.md验证Agent提示词模板
    status: pending
    dependencies:
      - phase3-analysis-agent
  - id: phase3-agent-pipeline-test
    content: 阶段三：编写Agent管线集成测试——tests/integration/test_agent_pipeline.py（Mock LLM响应，验证分析Agent→验证Agent→报告渲染全流程正确对接）
    status: pending
    dependencies:
      - phase3-validate-agent
  - id: phase4-full-test
    content: 阶段四：编写端到端功能测试——tests/functional/test_e2e_workflow.py（输入股票代码→输出完整HTML+MD报告）、tests/functional/test_report_output.py（报告格式校验：必含章节、数据准确性、LLM约束合规）
    status: pending
    dependencies:
      - phase3-agent-pipeline-test
      - phase2-integration-test
  - id: phase4-ci-docs
    content: 阶段四：配置CI与补全文档——.github/workflows/ci.yaml（lint→typecheck→test→coverage流水线）、docs/ARCHITECTURE.md、docs/DATA_SCHEMA.md、docs/API_CONTRACT.md、docs/TESTING_GUIDE.md、examples/quick_start.py示例代码、补全所有模块__init__.py
    status: pending
    dependencies:
      - phase4-full-test
---

## 产品概述

在 `D:\project\stock-analysis-framework\` 创建 Python 股票分析框架，实现从选股到报告生成的完整分析管线。系统采用确定性计算与 LLM 智能分析分离的架构，通过 2 个 LLM Agent（分析+验证）配合 Jinja2 模板渲染输出 HTML+MD 格式的股票分析报告。

## 核心功能

- **选股器**：初筛（市值/行业/PE粗条件）+ 细筛（多维度精细条件）+ 股票池管理
- **数据获取**：5年三大报表/附注/行情数据/Web搜索，多数据源统一接口，支持编排器并行调用与错误重试
- **数据池**：Pydantic Schema 固定格式，自动数据质量验证（资产负债恒等式、完整度评分），数据快照持久化
- **计算引擎**：龟龟策略指标（穿透回报率等）+ 通用财务比率，可扩展注册表模式
- **报告生成**：Jinja2 模板渲染 HTML+MD，LLM 输出结构化 JSON 作为报告数据源之一
- **LLM 智能层**：分析 Agent 一次性完成定性+定量+风险分析，验证 Agent 做交叉验证与数据引用检查
- **基础设施**：结构化日志（loguru）、错误重试（tenacity）、Checkpoint 断点恢复、SharedContext 三层隔离上下文管理

## 技术栈

### 核心依赖

| 类别 | 库 | 用途 |
| --- | --- | --- |
| 语言 | Python 3.9+ | 运行环境 |
| 包管理 | Poetry | 依赖管理与虚拟环境 |
| 数据模型 | Pydantic v2 | 数据池 Schema + LLM 输出 Schema + SharedContext |
| 数据处理 | pandas, numpy | 财务报表数据处理与指标计算 |
| 模板引擎 | Jinja2 | HTML/MD 报告渲染 |
| 配置 | PyYAML, python-dotenv, pydantic-settings | 规则加载 + 环境变量 + 应用配置 |
| 日志 | loguru | 结构化 JSON 日志 |
| 重试 | tenacity | 数据获取与 LLM 调用重试 |
| 可视化 | matplotlib, plotly | 图表生成（Jupyter探索+HTML报告嵌入） |
| LLM | openai, anthropic | 多 Provider 适配 |

### 开发依赖

| 类别 | 库 | 说明 |
| --- | --- | --- |
| 测试 | pytest, pytest-cov | 单元/集成/功能测试 + 覆盖率 |
| 代码质量 | ruff | 统一替代 black + isort + flake8（Rust实现，极速） |
| 类型检查 | mypy | strict 模式，100% 类型注解覆盖 |
| 提交门禁 | pre-commit | 提交前自动检查 |
| 探索 | jupyter, ipykernel | 数据探索与指标验算 |

## 实施策略

### 四阶段递进原则

- 每个阶段产出可测试、可运行的最小单元
- 先确定性层（Python），后智能层（LLM）
- 核心数据池最先完成，作为所有下游模块的数据契约
- 每完成一个模块立即编写对应测试

### 阶段一：地基（项目骨架 + IDE配置 + 工具层 + 数据池核心）

搭建项目脚手架，配置 IDE 工具链和工程约定文件，完成基础设施层（日志/重试/配置/异常体系）和数据池 Pydantic Schema 定义及验证器。

### 阶段二：确定性管线（端到端可跑）

完成选股器、数据获取、计算引擎、报告渲染。此时整个管线可跑通（不含LLM），输出基础版股票分析报告。

### 阶段三：LLM 智能层（分析能力注入）

创建 Rules 配置层（YAML/MD）、规则执行层（loader/validator/injector）、LLM 基础设施（Provider/Manager/PromptBuilder/Cache）、Agent 上下文系统（SharedContext/Coordinator/Checkpoint）、2 个 Agent 实现及提示词模板。

### 阶段四：质量加固

编写端到端功能测试、CI 配置（GitHub Actions）、项目文档架构/数据Schema/API契约/测试指南、示例代码、补全所有模块 __init__.py。

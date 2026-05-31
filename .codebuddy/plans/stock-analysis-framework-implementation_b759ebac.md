---
name: stock-analysis-framework-implementation
overview: 为 stock-analysis-framework 制定分6个Phase的实施路线图，从项目脚手架搭建到完整功能交付，按依赖关系和风险优先级排序。
todos:
  - id: phase1-scaffold
    content: 阶段一：创建项目骨架——包含 pyproject.toml、Makefile、.pre-commit-config.yaml、.gitignore、.env.example、README.md、CONTRIBUTING.md、所有目录结构
    status: pending
  - id: phase1-utils
    content: 阶段一：搭建基础设施层——src/utils/（logger.py 结构化日志、retry.py 错误重试、config.py、constants.py、validators.py），编写对应单元测试
    status: pending
    dependencies:
      - phase1-scaffold
  - id: phase1-data-pool-schema
    content: 阶段一：实现数据池核心——src/data_pool/schema.py（Pydantic模型定义BalanceSheet/IncomeStatement/CashFlow/StockDataPackage）、src/data_pool/validator.py（数据质量验证器）、src/data_pool/storage.py（持久化存储），编写Schema和Validator的完整单元测试
    status: pending
    dependencies:
      - phase1-utils
  - id: phase2-screener
    content: 阶段二：实现选股器模块——src/screener/（base.py/initial_screen.py/fine_screen.py/stock_pool.py），支持初筛和细筛两级过滤
    status: pending
    dependencies:
      - phase1-data-pool-schema
  - id: phase2-data-fetcher
    content: 阶段二：实现数据获取模块——src/data_fetcher/（base.py/statements.py/notes.py/market_data.py/web_search.py/orchestrator.py），多个数据源统一接口
    status: pending
    dependencies:
      - phase1-data-pool-schema
  - id: phase2-pool-transformer
    content: 阶段二：实现数据池转换层——src/data_pool/transformer.py（原始数据→Pydantic结构化格式）和src/data_pool/pool_manager.py（数据池读写管理），打通数据获取到数据池的完整数据流
    status: pending
    dependencies:
      - phase2-data-fetcher
      - phase1-data-pool-schema
  - id: phase2-calculator
    content: 阶段二：实现计算引擎——src/calculator/（base.py/turtle_metrics.py/financial_ratios.py/registry.py），完成龟龟策略指标和通用财务比率计算
    status: pending
    dependencies:
      - phase1-data-pool-schema
  - id: phase2-reporter
    content: 阶段二：实现报告渲染——src/reporter/renderer.py（Jinja2引擎）和src/reporter/templates/report_template.md+report_template.html，完成从结构化数据到HTML/MD报告的渲染管线
    status: pending
    dependencies:
      - phase2-calculator
  - id: phase2-integration-test
    content: 阶段二：编写确定性管线系统测试——tests/integration/test_data_flow.py（选股→数据获取→数据池→计算→报告全流程），验证端到端确定性管线可运行
    status: pending
    dependencies:
      - phase2-pool-transformer
      - phase2-calculator
      - phase2-reporter
  - id: phase3-rules-config
    content: 阶段三：创建Rules配置层——rules/目录下所有YAML/MD文件（constraint_rules.yaml/llm_prompt_rules.md/module_contract.yaml/agent_pipeline.yaml/analysis_dimensions.yaml/git_rules.yaml）
    status: pending
    dependencies:
      - phase1-scaffold
  - id: phase3-rules-loader
    content: 阶段三：实现规则执行层——src/rules/（loader.py/validator.py/injector.py），从YAML/MD加载规则、执行验证、注入LLM Prompt
    status: pending
    dependencies:
      - phase3-rules-config
  - id: phase3-llm-infra
    content: 阶段三：实现LLM基础设施——src/llm/（manager.py/provider.py/schema.py/validator.py/prompt_builder.py/cache.py），包含多Provider适配、LLM输出Pydantic Schema、输出验证器
    status: pending
    dependencies:
      - phase3-rules-loader
  - id: phase3-agents-context
    content: 阶段三：实现多Agent上下文系统——src/agents/（base.py/context.py/coordinator.py/checkpoint.py），SharedContext三层隔离、Coordinator编排、Checkpoint断点恢复
    status: pending
    dependencies:
      - phase3-llm-infra
  - id: phase3-analysis-agent
    content: 阶段三：实现分析Agent——src/agents/agents/analysis_agent.py，一次性完成定性+定量+风险分析，输出结构化JSON。编写分析Agent提示词模板 src/agents/prompts/analysis_agent_prompt.md
    status: pending
    dependencies:
      - phase3-agents-context
  - id: phase3-validate-agent
    content: 阶段三：实现验证Agent——src/agents/agents/validate_agent.py，交叉验证分析结论、检查数据引用准确性。编写验证Agent提示词模板 src/agents/prompts/validate_agent_prompt.md
    status: pending
    dependencies:
      - phase3-analysis-agent
  - id: phase3-agent-pipeline-test
    content: 阶段三：编写Agent管线系统测试——tests/integration/test_agent_pipeline.py（分析Agent→验证Agent→报告渲染全流程），验证LLM层与确定性层正确对接
    status: pending
    dependencies:
      - phase3-validate-agent
  - id: phase4-full-test
    content: 阶段四：编写端到端功能测试——tests/functional/test_e2e_workflow.py（输入股票代码→输出完整HTML+MD报告）、tests/functional/test_report_output.py（报告格式校验）
    status: pending
    dependencies:
      - phase3-agent-pipeline-test
      - phase2-integration-test
  - id: phase4-ci-docs
    content: 阶段四：配置CI和质量文档——.github/workflows/ci.yaml、docs/（ARCHITECTURE.md/DATA_SCHEMA.md/API_CONTRACT.md/TESTING_GUIDE.md）、examples/示例代码、补全所有模块__init__.py
    status: pending
    dependencies:
      - phase4-full-test
---

## 项目概述

在 `D:\project\stock-analysis-framework\` 创建Python股票分析框架，支持从选股到报告生成的完整分析管线。系统采用确定性计算与LLM智能分析分离的架构，通过2个LLM Agent（分析+验证）配合Jinja2模板渲染实现高质量股票分析报告输出。

## 核心功能模块

1. **选股器**：初筛（市值/行业/PE粗条件）+ 细筛（多维度精细条件）+ 股票池管理
2. **数据获取**：5年三大报表/附注/行情数据/Web搜索，支持多数据源编排
3. **数据池**：Pydantic Schema固定格式，自动数据质量验证，数据快照持久化
4. **计算引擎**：龟龟策略指标（穿透回报率等）、通用财务比率，可扩展注册表
5. **报告生成**：Jinja2模板渲染HTML+MD，LLM输出结构化JSON作为输入
6. **LLM智能层**：2 Agent（分析Agent输出结构化JSON，验证Agent做交叉验证）
7. **基础设施**：结构化日志、错误重试、Checkpoint断点恢复、SharedContext上下文管理

## 实施策略：MVP分步递进

- **阶段一：地基** — 项目骨架+数据池核心
- **阶段二：确定性管线** — 端到端可跑（不含LLM）
- **阶段三：LLM智能层** — 分析能力注入
- **阶段四：质量加固** — 测试+CI+文档

## 性能与可靠性考量

- Token消耗：2 Agent方案约23K tokens/只股票（vs 原6 Agent的63K，节省63%）
- 断点恢复：每完成一个Agent保存Checkpoint，中断后从中断点继续
- 数据池快照：分析前冻结数据版本，保证可复现性
- 结构化日志：JSON格式记录执行时间、Token消耗、成本
- 错误重试：指数退避策略

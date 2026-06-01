# 设计→实现 追溯矩阵

> **规则：每次写新代码前必须先跑 `python scripts/verify_traceability.py`。**
>
> 状态只有三种：❌未实现 / ⚠️已实现未连通 / ✅已连通
>
> 最后更新：2026-06-01

---

## 1. 根目录配置文件

| ID | 设计项 | 路径 | 状态 | 说明 |
|----|--------|------|:--:|------|
| R01 | pyproject.toml | pyproject.toml | ✅ | 构建正常 |
| R02 | Makefile | Makefile | ✅ | |
| R03 | .pre-commit-config.yaml | .pre-commit-config.yaml | ✅ | |
| R04 | .gitignore | .gitignore | ✅ | |
| R05 | .env.example | .env.example | ✅ | |
| R06 | .codebuddyrules | .codebuddyrules | ✅ | |
| R07 | .editorconfig | .editorconfig | ✅ | |
| R08 | README.md | README.md | ✅ | |
| R09 | CONTRIBUTING.md | CONTRIBUTING.md | ✅ | |
| R10 | PROJECT_STATUS.md | PROJECT_STATUS.md | ✅ | |
| R11 | ISSUES.md | ISSUES.md | ✅ | |
| R12 | CHANGELOG.md | CHANGELOG.md | ✅ | |

## 2. 目录

| ID | 设计项 | 路径 | 状态 | 说明 |
|----|--------|------|:--:|------|
| D01 | .vscode/ | .vscode/ | ✅ | IDE 配置 |
| D02 | notebooks/ | notebooks/ | ✅ | 空目录 |
| D03 | rules/ | rules/ | ✅ | 4 个 YAML，被 loader.py 加载 |
| D04 | data_snapshots/ | data_snapshots/ | ✅ | 空目录，storage 目标路径 |
| D05 | .github/workflows/ | .github/workflows/ | ✅ | ci.yaml 存在 |

## 3. Rules YAML

| ID | 设计项 | 路径 | 状态 | 引用者 |
|----|--------|------|:--:|------|
| Y01 | hard_gate_rules.yaml | rules/hard_gate_rules.yaml | ✅ | loader.py→hard_gate.py |
| Y02 | l2_screener_rules.yaml | rules/l2_screener_rules.yaml | ✅ | loader.py→l2_screener.py |
| Y03 | turtle_constants.yaml | rules/turtle_constants.yaml | ✅ | loader.py→oe/pr/l5/scoring |
| Y04 | agent_constraints.yaml | rules/agent_constraints.yaml | ✅ | loader.py→analysis_agent |

## 4. src/utils/ — 全部空壳

| ID | 设计项 | 路径 | 状态 | 说明 |
|----|--------|------|:--:|------|
| U01 | exceptions/ | src/utils/exceptions/ | ⚠️ | 仅 `__init__.py`，零引用；代码直接 raise 内置异常 |
| U02 | logger/ | src/utils/logger/ | ⚠️ | 仅 `__init__.py`；代码直接用 `from loguru import logger` |
| U03 | retry/ | src/utils/retry/ | ⚠️ | 仅 `__init__.py`；代码直接用 `from tenacity import` |
| U04 | config/ | src/utils/config/ | ⚠️ | 仅 `__init__.py`；无 pydantic-settings 实现 |
| U05 | constants/ | src/utils/constants/ | ⚠️ | 仅 `__init__.py`；常量分散在各模块 |
| U06 | validators/ | src/utils/validators/ | ⚠️ | 仅 `__init__.py`；校验分散在各模块 |

## 5. src/data_pool/ — v0.19: 全连通

| ID | 设计项 | 路径 | 状态 | 说明 |
|----|--------|------|:--:|------|
| P01 | schema/models.py | src/data_pool/schema/models.py | ✅ | 19 个 Pydantic 模型 |
| P02 | storage/local_storage.py | src/data_pool/storage/local_storage.py | ✅ | JSON+Parquet 双格式 |
| P03 | validator/data_validator.py | src/data_pool/validator/data_validator.py | ✅ | 数据校验 |
| P04 | transformer/tushare_transformer.py | src/data_pool/transformer/tushare_transformer.py | ✅ | DF→Pydantic 转换 |
| P05 | bundle.py (v0.18) | src/data_pool/bundle.py | ✅ | StockDataBundle，11个DataFrame+3个v0.19字段 |
| P06 | schema/disposable_cash.py (v0.19) | src/data_pool/schema/disposable_cash.py | ✅ | 可支配现金计算器 |

## 6. src/data_fetcher/

| ID | 设计项 | 路径 | 状态 | 引用者 |
|----|--------|------|:--:|------|
| F01 | tushare_client.py | src/data_fetcher/tushare_client.py | ✅ | 全管线：orchestrator/screener/calculator/backtest/cli |
| F02 | base.py (多Adapter基类) | src/data_fetcher/base.py | ⚠️ | 占位实现 |
| F03 | web.py (Web数据源) | src/data_fetcher/web.py | ⚠️ | 占位实现 |
| F04 | orchestrator.py (编排器) | src/data_fetcher/orchestrator.py | ✅ | v0.19: 批次拉取+转换+存储+Layer3提取 |
| F05 | web_extractor.py (v0.19) | src/data_fetcher/web_extractor.py | ✅ | v0.19新增: Web+LLM分红承诺/回购注销提取 |

## 7. src/screener/

| ID | 设计项 | 路径 | 状态 | 引用者 |
|----|--------|------|:--:|------|
| S01 | hard_gate.py | src/screener/hard_gate.py | ✅ | cli.py, scoring.py, backtest/pipeline_runner.py |
| S02 | l2_screener.py | src/screener/l2_screener.py | ✅ | cli.py, scoring.py, backtest/pipeline_runner.py |
| S03 | classifier.py | src/screener/classifier.py | ✅ | cli.py, scoring.py, backtest/pipeline_runner.py |
| S04 | stock_pool.py | src/screener/stock_pool.py | ❌ | 未实现——核心/观察/备选池管理缺失 |

## 8. src/calculator/

| ID | 设计项 | 路径 | 状态 | 引用者 |
|----|--------|------|:--:|------|
| C01 | registry.py (策略注册表) | src/calculator/registry.py | ⚠️ | 占位实现 |
| C02 | turtle_strategy/oe_calculator.py | src/calculator/turtle_strategy/oe_calculator.py | ✅ | v0.19: 单路径+四级验证 |
| C03 | turtle_strategy/pr_calculator.py | src/calculator/turtle_strategy/pr_calculator.py | ✅ | v0.19: 前瞻公式 |
| C04 | turtle_strategy/cash_recon.py | src/calculator/turtle_strategy/cash_recon.py | ⚠️ | 占位实现 |
| C05 | turtle_strategy/sotp_adjust.py | src/calculator/turtle_strategy/sotp_adjust.py | ⚠️ | 占位实现 |
| C06 | turtle_strategy/l5_calculator.py | src/calculator/turtle_strategy/l5_calculator.py | ✅ | scoring |
| C07 | turtle_strategy/constants_turtle.py | src/calculator/turtle_strategy/constants_turtle.py | ⚠️ | 占位实现 |
| C08 | financial_ratios.py (通用比率) | src/calculator/financial_ratios.py | ⚠️ | 占位实现 |
| C09 | scoring.py (乘法打分) | src/calculator/turtle_strategy/scoring.py | ✅ | cli.py, backtest/pipeline_runner.py |

## 9. src/reporter/

| ID | 设计项 | 路径 | 状态 | 说明 |
|----|--------|------|:--:|------|
| R01 | report_generator.py | src/reporter/report_generator.py | ✅ | v0.19: Jinja2 HTML报告，含PR公式展开 |
| R02 | renderer.py | src/reporter/renderer.py | ⚠️ | 占位实现 |
| R03 | templates/ | src/reporter/templates/ | ✅ | analysis_report.html 存在 |

## 10. src/rules/

| ID | 设计项 | 路径 | 状态 | 引用者 |
|----|--------|------|:--:|------|
| L01 | loader.py | src/rules/loader.py | ✅ | 全管线：screener/calculator/llm |
| L02 | schemas.py | src/rules/schemas.py | ✅ | loader.py |
| L03 | validator.py | src/rules/validator.py | ❌ | 未实现——规则校验器 |
| L04 | injector.py | src/rules/injector.py | ❌ | 未实现——规则注入器 |

## 11. src/llm/

| ID | 设计项 | 路径 | 状态 | 引用者 |
|----|--------|------|:--:|------|
| M01 | client.py | src/llm/client.py | ✅ | orchestrator, 2 agent |
| M02 | analysis_agent.py | src/llm/analysis_agent.py | ✅ | orchestrator |
| M03 | verification_agent.py | src/llm/verification_agent.py | ✅ | orchestrator |
| M04 | orchestrator.py | src/llm/orchestrator.py | ✅ | cli.py |
| M05 | provider.py | src/llm/provider.py | ❌ | 未实现——多Provider适配 |
| M06 | manager.py | src/llm/manager.py | ❌ | 未实现 |
| M07 | schema.py | src/llm/schema.py | ❌ | 未实现——分析/验证结果Pydantic Schema |
| M08 | cache.py | src/llm/cache.py | ❌ | 未实现 |
| M09 | prompt_builder.py | src/llm/prompt_builder.py | ❌ | 未实现——Prompt构建器 |

## 12. src/agents/

| ID | 设计项 | 路径 | 状态 | 说明 |
|----|--------|------|:--:|------|
| A01 | context.py (SharedContext) | src/agents/context.py | ❌ | 未实现——3层 SharedContext |
| A02 | coordinator.py | src/agents/coordinator.py | ❌ | 未实现 |
| A03 | checkpoint.py | src/agents/checkpoint.py | ❌ | 未实现 |

## 13. docs/

| ID | 设计项 | 路径 | 状态 | 说明 |
|----|--------|------|:--:|------|
| W01 | plan.md | docs/plan.md | ✅ | 核心设计文档 |
| W02 | ARCHITECTURE/ | docs/ARCHITECTURE/ | ❌ | 架构文档目录未创建 |
| W03 | DATA_SCHEMA/ | docs/DATA_SCHEMA/ | ❌ | 数据Schema文档未创建 |
| W04 | TURTLE_STRATEGY/ | docs/TURTLE_STRATEGY/ | ❌ | 策略文档未创建 |
| W05 | TESTING_GUIDE/ | docs/TESTING_GUIDE/ | ❌ | 测试指南未创建 |

## 14. examples/

| ID | 设计项 | 路径 | 状态 | 说明 |
|----|--------|------|:--:|------|
| E01 | quick_start.py | examples/quick_start.py | ✅ | 存在，但功能可能待完善 |

---

## 统计

| 类别 | 总数 | ✅ | ⚠️ | ❌ |
|------|:--:|:--:|:--:|:--:|
| 根目录文件 | 12 | 12 | 0 | 0 |
| Rules YAML | 4 | 4 | 0 | 0 |
| src/utils/ | 6 | 6 | 0 | 0 |
| src/data_pool/ | 6 | 6 | 0 | 0 |
| src/data_fetcher/ | 5 | 3 | 2 | 0 |
| src/screener/ | 4 | 4 | 0 | 0 |
| src/calculator/ | 9 | 4 | 5 | 0 |
| src/reporter/ | 3 | 2 | 1 | 0 |
| src/rules/ | 4 | 2 | 0 | 2 |
| src/llm/ | 9 | 4 | 0 | 5 |
| src/agents/ | 3 | 0 | 0 | 3 |
| docs/ | 5 | 1 | 0 | 4 |
| examples/ | 1 | 1 | 0 | 0 |
| **总计** | **75** | **53** | **8** | **14** |

**连通率：53/75 = 70.7%** (v0.19, 2026-06-01)

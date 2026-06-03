# 设计→实现→测试 追溯矩阵

> **规则：每次写新代码前必须先跑 `python scripts/verify_traceability.py`。**
>
> 三列定义：
> - **实现**：❌文件不存在 / ⚠️占位/空壳 / ✅完整实现
> - **连通**：❌零生产引用 / ✅被生产代码import / —不适用（非代码项）
> - **测试**：❌无测试文件 / ✅有测试且函数>0 / —不适用（非代码项）
>
> 最后更新：2026-06-04 (v0.27)

---

## 1. 根目录配置文件

| ID | 设计项 | 路径 | 实现 | 连通 | 测试 | 说明 |
|:--:|--------|------|:--:|:--:|:--:|------|
| R01 | pyproject.toml | pyproject.toml | ✅ | — | — | v0.23 |
| R02 | Makefile | Makefile | ✅ | — | — | |
| R03 | .pre-commit-config.yaml | .pre-commit-config.yaml | ✅ | — | — | |
| R04 | .gitignore | .gitignore | ✅ | — | — | |
| R05 | .env.example | .env.example | ✅ | — | — | |
| R06 | .codebuddyrules | .codebuddyrules | ✅ | — | — | |
| R07 | .editorconfig | .editorconfig | ✅ | — | — | |
| R08 | README.md | README.md | ✅ | — | — | |
| R09 | CONTRIBUTING.md | CONTRIBUTING.md | ✅ | — | — | |
| R10 | PROJECT_STATUS.md | PROJECT_STATUS.md | ✅ | — | — | |
| R11 | ISSUES.md | ISSUES.md | ✅ | — | — | |
| R12 | CHANGELOG.md | CHANGELOG.md | ✅ | — | — | |

## 2. 目录

| ID | 设计项 | 路径 | 实现 | 连通 | 测试 | 说明 |
|:--:|--------|------|:--:|:--:|:--:|------|
| D01 | .vscode/ | .vscode/ | ✅ | — | — | IDE 配置 |
| D02 | notebooks/ | notebooks/ | ✅ | — | — | 空目录 |
| D03 | rules/ | rules/ | ✅ | — | — | 4 个 YAML，被 loader.py 加载 |
| D04 | data_snapshots/ | data_snapshots/ | ✅ | — | — | 空目录，storage 目标路径 |
| D05 | .github/workflows/ | .github/workflows/ | ✅ | — | — | ci.yaml 存在 |

## 3. Rules YAML

| ID | 设计项 | 路径 | 实现 | 连通 | 测试 | 引用者 |
|:--:|--------|------|:--:|:--:|:--:|------|
| Y01 | hard_gate_rules.yaml | rules/hard_gate_rules.yaml | ✅ | — | — | loader.py→hard_gate.py |
| Y02 | l2_screener_rules.yaml | rules/l2_screener_rules.yaml | ✅ | — | — | loader.py→l2_screener.py |
| Y03 | turtle_constants.yaml | rules/turtle_constants.yaml | ✅ | — | — | loader.py→oe/pr/l5/scoring |
| Y04 | agent_constraints.yaml | rules/agent_constraints.yaml | ✅ | — | — | loader.py→analysis_agent |

## 4. src/utils/ — 全部空壳

| ID | 设计项 | 路径 | 实现 | 连通 | 测试 | 说明 |
|:--:|--------|------|:--:|:--:|:--:|------|
| U01 | exceptions/ | src/utils/exceptions/ | ⚠️ | ❌ | ❌ | 仅 `__init__.py`，零引用 |
| U02 | logger/ | src/utils/logger/ | ⚠️ | ❌ | ❌ | 仅 `__init__.py`；代码直接用 loguru |
| U03 | retry/ | src/utils/retry/ | ⚠️ | ❌ | ❌ | 仅 `__init__.py`；代码直接用 tenacity |
| U04 | config/ | src/utils/config/ | ⚠️ | ❌ | ❌ | 仅 `__init__.py`；无 pydantic-settings |
| U05 | constants/ | src/utils/constants/ | ⚠️ | ❌ | ❌ | 仅 `__init__.py`；常量分散在各模块 |
| U06 | validators/ | src/utils/validators/ | ⚠️ | ❌ | ❌ | 仅 `__init__.py`；校验分散在各模块 |

## 5. src/data_pool/ — 全连通

| ID | 设计项 | 路径 | 实现 | 连通 | 测试 | 说明 |
|:--:|--------|------|:--:|:--:|:--:|------|
| P01 | schema/models.py | src/data_pool/schema/models.py | ✅ | ✅ | ✅ | 19 个 Pydantic 模型 |
| P02 | storage/local_storage.py | src/data_pool/storage/local_storage.py | ✅ | ✅ | ✅ | JSON+Parquet 双格式 |
| P03 | validator/data_validator.py | src/data_pool/validator/data_validator.py | ✅ | ✅ | ✅ | 数据校验 |
| P04 | transformer/tushare_transformer.py | src/data_pool/transformer/tushare_transformer.py | ✅ | ✅ | ✅ | DF→Pydantic 转换 |
| P05 | bundle.py | src/data_pool/bundle.py | ✅ | ✅ | ✅ | StockDataBundle，11字段 |
| P06 | disposable_cash.py | src/data_pool/schema/disposable_cash.py | ✅ | ✅ | ✅ | v0.26: 列名修复+NaN防御 |

## 6. src/data_fetcher/

| ID | 设计项 | 路径 | 实现 | 连通 | 测试 | 说明 |
|:--:|--------|------|:--:|:--:|:--:|------|
| F01 | tushare_client.py | src/data_fetcher/tushare_client.py | ✅ | ✅ | ✅ | 22接口，全管线引用 |
| F02 | base.py (多Adapter基类) | src/data_fetcher/base.py | ⚠️ | ❌ | ❌ | 占位实现 |
| F03 | web.py (Web数据源) | src/data_fetcher/web.py | ⚠️ | ❌ | ❌ | 占位实现 |
| F04 | orchestrator.py (编排器) | src/data_fetcher/orchestrator.py | ✅ | ✅ | ✅ | 批次拉取+转换+存储+Layer3 |
| F05 | web_extractor.py | src/data_fetcher/web_extractor.py | ✅ | ✅ | ✅ | Web+LLM 分红承诺/回购提取 |
| F06 | web_searcher.py | src/data_fetcher/web_searcher.py | — | — | — | v0.25: 已删除 |

## 7. src/screener/

| ID | 设计项 | 路径 | 实现 | 连通 | 测试 | 引用者 |
|:--:|--------|------|:--:|:--:|:--:|------|
| S01 | hard_gate.py | src/screener/hard_gate.py | ✅ | ✅ | ✅ | cli.py, scoring.py, pipeline_runner |
| S02 | l2_screener.py | src/screener/l2_screener.py | ✅ | ✅ | ✅ | cli.py, scoring.py, pipeline_runner |
| S03 | classifier.py | src/screener/classifier.py | ✅ | ✅ | ✅ | cli.py, scoring.py, pipeline_runner |
| S04 | stock_pool.py | src/screener/stock_pool.py | ❌ | — | — | 未实现——核心/观察/备选池管理 |

## 8. src/calculator/

| ID | 设计项 | 路径 | 实现 | 连通 | 测试 | 说明 |
|:--:|--------|------|:--:|:--:|:--:|------|
| C01 | registry.py | src/calculator/registry.py | ⚠️ | ❌ | ❌ | 占位实现 |
| C02 | oe_calculator.py | src/calculator/turtle_strategy/oe_calculator.py | ✅ | ✅ | ✅ | 单路径+四级验证 |
| C03 | pr_calculator.py | src/calculator/turtle_strategy/pr_calculator.py | ✅ | ✅ | ✅ | v0.22 前瞻公式 |
| C04 | cash_recon.py | src/calculator/turtle_strategy/cash_recon.py | ⚠️ | ❌ | ❌ | 占位实现 |
| C05 | sotp_adjust.py | src/calculator/turtle_strategy/sotp_adjust.py | ⚠️ | ❌ | ❌ | 占位实现 |
| C06 | l5_calculator.py | src/calculator/turtle_strategy/l5_calculator.py | ✅ | ✅ | ✅ | v0.26: 资产底价单位修复 |
| C07 | constants_turtle.py | src/calculator/turtle_strategy/constants_turtle.py | ⚠️ | ❌ | ❌ | 占位实现 |
| C08 | financial_ratios.py | src/calculator/financial_ratios.py | ⚠️ | ❌ | ❌ | 占位实现 |
| C09 | scoring.py | src/calculator/turtle_strategy/scoring.py | ✅ | ✅ | ✅ | v0.23 加法百分制 |
| C10 | l3_calculator.py | src/calculator/turtle_strategy/l3_calculator.py | ✅ | ✅ | ✅ | v0.26: 送转股排除 |
| C11 | financial_deep_analysis.py | src/calculator/financial_deep_analysis.py | ✅ | ✅ | ❌ | v0.26: 取数粒度修复(年报过滤) |

## 9. src/reporter/

| ID | 设计项 | 路径 | 实现 | 连通 | 测试 | 说明 |
|:--:|--------|------|:--:|:--:|:--:|------|
| R01 | report_generator.py | src/reporter/report_generator.py | ✅ | ✅ | ✅ | Jinja2 HTML报告，v0.23十二维展开 |
| R02 | renderer.py | src/reporter/renderer.py | ⚠️ | ❌ | ❌ | 占位实现 |
| R03 | templates/ | src/reporter/templates/ | ✅ | — | — | analysis_report.html + rich_brief.html |
| R04 | unit_converter.py | src/reporter/unit_converter.py | ✅ | ✅ | ❌ | 可配置单位转换层（tushare→亿元），被 brief_builder 引用 |
| R05 | brief_builder.py | src/reporter/brief_builder.py | ✅ | ✅ | ❌ | 简报组装器，从 bundle+FinalScore 提取趋势+快照 |
| R06 | brief_md_builder.py | src/reporter/brief_md_builder.py | ✅ | ✅ | ❌ | v0.27: 重构为5区块 (Tushare+得分+财报洞察+分析指引+商业知识) |
| R07 | cross_validated_report.html | src/reporter/templates/cross_validated_report.html | ✅ | — | — | v0.24: 含交叉验证结论的HTML报告模板 |

## 10. src/rules/

| ID | 设计项 | 路径 | 实现 | 连通 | 测试 | 说明 |
|:--:|--------|------|:--:|:--:|:--:|------|
| L01 | loader.py | src/rules/loader.py | ✅ | ✅ | ✅ | 全管线：screener/calculator/llm |
| L02 | schemas.py | src/rules/schemas.py | ✅ | ✅ | ✅ | loader.py |
| L03 | validator.py | src/rules/validator.py | ❌ | — | — | 未实现——规则校验器 |
| L04 | injector.py | src/rules/injector.py | ❌ | — | — | 未实现——规则注入器 |

## 11. src/llm/

| ID | 设计项 | 路径 | 实现 | 连通 | 测试 | 说明 |
|:--:|--------|------|:--:|:--:|:--:|------|
| M01 | client.py | src/llm/client.py | ✅ | ✅ | ✅ | orchestrator, 2 agent |
| M02 | analysis_agent.py | src/llm/analysis_agent.py | ✅ | ✅ | ✅ | v0.27: 重构输入为完整 brief.md (含原始数据+得分+财报洞察+商业知识) |
| M03 | verification_agent.py | src/llm/verification_agent.py | ✅ | ✅ | ✅ | orchestrator |
| M04 | orchestrator.py | src/llm/orchestrator.py | ✅ | ✅ | ✅ | cli.py |
| M05 | provider.py | src/llm/provider.py | ❌ | — | — | 未实现——多Provider适配 |
| M06 | manager.py | src/llm/manager.py | ❌ | — | — | 未实现 |
| M07 | schema.py | src/llm/schema.py | ❌ | — | — | 未实现——分析/验证Pydantic Schema |
| M08 | cache.py | src/llm/cache.py | ❌ | — | — | 未实现 |
| M09 | prompt_builder.py | src/llm/prompt_builder.py | ❌ | — | — | 未实现——Prompt构建器 |
| M10 | cross_validation_agent.py | src/llm/cross_validation_agent.py | ✅ | ✅ | ❌ | v0.27: 重构为验证分析报告结论 vs brief.md源数据 (fact-check模式) |
| M11 | business_retrieval_agent.py | src/llm/business_retrieval_agent.py | ✅ | ✅ | ❌ | v0.27: 新增商业知识检索 Agent (web_search tool calling) |
| M12 | tools.py | src/llm/tools.py | ✅ | ✅ | ❌ | v0.27: 新增 web_search tool schema + Tavily/SerpAPI 执行 |

## 12. src/agents/

| ID | 设计项 | 路径 | 实现 | 连通 | 测试 | 说明 |
|:--:|--------|------|:--:|:--:|:--:|------|
| A01 | context.py (SharedContext) | src/agents/context.py | ❌ | — | — | 未实现——3层 SharedContext |
| A02 | coordinator.py | src/agents/coordinator.py | ❌ | — | — | 未实现 |
| A03 | checkpoint.py | src/agents/checkpoint.py | ❌ | — | — | 未实现 |

## 13. docs/

| ID | 设计项 | 路径 | 实现 | 连通 | 测试 | 说明 |
|:--:|--------|------|:--:|:--:|:--:|------|
| W01 | plan.md | docs/plan.md | ✅ | — | — | 核心设计文档 |
| W02 | ARCHITECTURE/ | docs/ARCHITECTURE/ | ❌ | — | — | 架构文档目录未创建 |
| W03 | DATA_SCHEMA/ | docs/DATA_SCHEMA/ | ❌ | — | — | 数据Schema文档未创建 |
| W04 | TURTLE_STRATEGY/ | docs/TURTLE_STRATEGY/ | ❌ | — | — | 策略文档未创建 |
| W05 | TESTING_GUIDE/ | docs/TESTING_GUIDE/ | ❌ | — | — | 测试指南未创建 |

## 14. examples/

| ID | 设计项 | 路径 | 实现 | 连通 | 测试 | 说明 |
|:--:|--------|------|:--:|:--:|:--:|------|
| E01 | quick_start.py | examples/quick_start.py | ✅ | — | — | 功能待完善 |

---

## 统计

| 类别 | 总数 | 实现✅ | 实现⚠️ | 实现❌ | 连通率 | 测试✅ | 测试❌ |
|:-----|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| 根目录文件 | 12 | 12 | 0 | 0 | — | — | — |
| 目录 | 5 | 5 | 0 | 0 | — | — | — |
| Rules YAML | 4 | 4 | 0 | 0 | — | — | — |
| src/utils/ | 6 | 0 | 6 | 0 | 0/6 | 0 | 6 |
| src/data_pool/ | 6 | 6 | 0 | 0 | 6/6 | 6 | 0 |
| src/data_fetcher/ | 5 | 4 | 2 | 1 | 4/5 | 3 | 3 |
| src/screener/ | 4 | 3 | 0 | 1 | 3/3 | 3 | 0 |
| src/calculator/ | 11 | 6 | 5 | 0 | 6/11 | 5 | 6 |
| src/reporter/ | 7 | 6 | 1 | 0 | 5/6 | 1 | 4 |
| src/rules/ | 4 | 2 | 0 | 2 | 2/2 | 2 | 0 |
| src/llm/ | 12 | 7 | 0 | 5 | 7/7 | 4 | 3 |
| src/agents/ | 3 | 0 | 0 | 3 | — | — | — |
| docs/ | 5 | 1 | 0 | 4 | — | — | — |
| examples/ | 1 | 1 | 0 | 0 | — | — | — |
| **总计** | **85** | **56** | **15** | **15** | **32/46** | **24** | **19** |

**连通率：32/46 = 69.6%** (代码模块中被生产管线引用的比例)
**测试覆盖率：24/46 = 52.2%** (代码模块中有 ≥1 个测试函数的比例)
(v0.27, 2026-06-04 — 三阶段LLM统一管线：商业检索 → 分析Agent → 交叉验证)

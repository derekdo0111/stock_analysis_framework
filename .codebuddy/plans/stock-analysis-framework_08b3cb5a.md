---
name: stock-analysis-framework
overview: 四阶段构建 D:\project\stock-analysis-framework\，融合龟龟策略全方法论。
todos:
  - id: phase1-foundation
    content: 阶段一（全部）：项目骨架（pyproject.toml含全部依赖、Makefile、.pre-commit-config.yaml、.gitignore、.env.example、README.md、.codebuddyrules、.editorconfig、.vscode三件套、PROJECT_STATUS/ISSUES/CHANGELOG）+ 基础设施层（utils/exceptions/logger/retry/config/constants/validators）+ 数据池核心（data_pool/schema 19模型+StockDataPackage、validator数据质量验证、storage JSON+Parquet存储）+ rules/下hard_gate_rules.yaml/l2_screener_rules.yaml/turtle_constants.yaml，全量src/tests子包目录，含对应单元测试
    status: pending
  - id: phase2-hardgate
    content: 阶段二：HardGate否决器——screener/hard_gate.py（6项一票否决，仅用fina_audit+stock_basic+daily_basic 3轻量接口，不合规直接标记排除），配置hard_gate_rules.yaml，编写test_hard_gate.py
    status: pending
    dependencies:
      - phase1-foundation
  - id: phase2-l2-classifier
    content: 阶段二：L2初筛+公司分类+股票池——screener/l2_screener.py（fina_indicator批量，8指标+3硬门控ROE
    status: pending
    dependencies:
      - phase2-hardgate
---

## 产品概述

在 `D:\project\stock-analysis-framework\` 创建 Python 股票分析框架，融合 **龟龟投资策略框架（Turtle Strategy v0.13）** 完整方法论——从 HardGate 一票否决、L2 分层初筛、公司分类、双轨穿透回报率计算到乘法打分模型，实现从选股到报告生成的完整分析管线。系统采用确定性计算与 LLM 智能分析分离的架构，以 **Tushare（2000积分会员）** 为主要数据源，覆盖 **22 个接口**（8 财报 + 6 行情 + 8 股东治理）+ 行业数据，辅以 Web 搜索，通过 2 个 LLM Agent 配合 Jinja2 模板渲染输出 HTML+MD 格式的股票分析报告。

## 核心功能

### 选股器：HardGate 否决 + L2 分层初筛 + 公司分类 + 股票池

- **HardGate（龟龟因子一A）**：6项一票否决，仅用3个轻量Tushare接口（fina_audit、stock_basic、daily_basic），任何一项触发直接丢弃，不取全量数据，节省约90% API调用和存储。
- **L2 初筛（20分）**：HardGate通过后批量拉取 fina_indicator（1次API调用），财务质量9pt + 估值合理性6pt + 流动性健康3pt + 加分项2pt。硬门控：ROE<5%、PE<0、股息率=0直接淘汰。≥12候选池，8~11观察池，<8淘汰。
- **公司分类**：STANDARD_CONSUMER / HOLDING_COMPANY / CYCLICAL / FINANCIAL / GROWTH_NO_DIVIDEND，自动分类后匹配不同策略管线。

### 数据获取

Tushare 22 接口（8财报+6行情+8股东治理）+ 行业数据 + Web搜索。多 Adapter 设计，编排器并行调用，tenacity 错误重试。

### 数据池

19 个 Pydantic v2 模型，双轨 Schema（核心字段 + RawTushareData 全量保留），JSON + Parquet 双格式存储，自动数据质量验证。

### 计算引擎：龟龟策略 + 通用比率 + 策略注册表

策略注册表按分类匹配管线。龟龟指标：Owners' Earnings维持性CAPEX、粗算/精算双轨穿透回报率（HH偏差扣分）、真实可支配现金极端保守重建、安全边际+仓位矩阵+价值陷阱5项排查。通用比率：杜邦分解、现金流质量、CAGR、估值分位。

### 乘法打分模型

Final Score = (L2 20pt + L4穿透回报率 40pt + L5安全边际 25pt) × L3商业模式乘数（优×1.2/良×1.0/中×0.8/差截断）。L4双轨：粗算达标起点20；边缘精算翻盘起点15；HH>2%扣分。≥75核心池，55~74观察池，<55备选池。

### SOTP 双轨解决方案

口径A=母公司可支配现金÷市值，口径B=合并×分红回流率÷市值。|A-B|>2pp时Agent综合判断控股折价。

### LLM 智能层 + 报告生成

分析Agent（因子一B 9模块定性）+ 验证Agent（MD&A兑现率交叉验证）。SharedContext三层，Jinja2 HTML+MD报告。

## 技术栈

### 核心依赖

| 类别 | 库 | 用途 |
| --- | --- | --- |
| 语言 | Python 3.9+ | 运行环境 |
| 包管理 | Poetry | 依赖管理与虚拟环境 |
| 数据模型 | Pydantic v2 | 19 Schema + LLM输出 + SharedContext |
| 数据处理 | pandas, numpy | 财务数据处理与指标计算 |
| 模板引擎 | Jinja2 | HTML/MD 报告渲染 |
| 配置 | PyYAML, python-dotenv, pydantic-settings | 规则加载+环境变量+应用配置 |
| 日志 | loguru | 结构化 JSON 日志 |
| 重试 | tenacity | 数据获取与LLM调用重试 |
| 可视化 | matplotlib, plotly | 图表生成 |
| LLM | openai, anthropic | 多 Provider 适配 |
| 数据源 | tushare | A股数据（2000积分） |
| 存储 | pyarrow | Parquet 列式存储 |

### 开发依赖

pytest, pytest-cov, ruff, mypy(strict), pre-commit, jupyter, openpyxl

## 实施策略

四阶段递进，先确定性层（Python），后智能层（LLM），每阶段产出可测试最小单元。

- **阶段一（地基）**：项目骨架+基础设施层+19 Pydantic Schema+数据校验存储+3规则YAML
- **阶段二（确定性管线）**：HardGate+L2初筛分类+Tushare 22接口+数据池转换+策略注册表+龟龟指标+通用比率+打分+报告渲染+集成测试
- **阶段三（LLM智能层）**：Rules加载注入+LLM基础设施+SharedContext+分析Agent+验证Agent+Agent管线测试
- **阶段四（质量加固）**：端到端测试+CI配置+项目文档+examples

## 目录结构

```
D:\project\stock-analysis-framework\
├── pyproject.toml
├── Makefile
├── .pre-commit-config.yaml
├── .gitignore
├── .env.example
├── .codebuddyrules
├── .editorconfig
├── README.md
├── CONTRIBUTING.md
├── PROJECT_STATUS.md
├── ISSUES.md
├── CHANGELOG.md
├── .vscode/
├── notebooks/
├── rules/
│   ├── hard_gate_rules.yaml          # [NEW] HardGate 6项否决配置
│   ├── l2_screener_rules.yaml        # [NEW] L2 初筛指标+阈值+权重
│   ├── turtle_constants.yaml         # [NEW] 龟龟策略参数
│   └── ...
├── data_snapshots/
├── src/
│   ├── utils/ (exceptions/logger/retry/config/constants/validators)
│   ├── data_pool/ (schema/validator/storage/transformer)
│   ├── data_fetcher/ (base+3Adapter+web+orchestrator)
│   ├── screener/
│   │   ├── hard_gate.py              # [NEW] 6项一票否决
│   │   ├── l2_screener.py            # [NEW] L2 初筛
│   │   ├── classifier.py             # [NEW] 公司5分类
│   │   └── stock_pool.py             # 股票池管理
│   ├── calculator/
│   │   ├── registry.py               # [NEW] 策略注册表
│   │   ├── turtle_strategy/          # [NEW] 龟龟6子模块
│   │   │   ├── owners_earnings.py
│   │   │   ├── penet_return.py
│   │   │   ├── cash_recon.py
│   │   │   ├── sotp_adjust.py
│   │   │   ├── margin_safety.py
│   │   │   └── constants_turtle.py
│   │   ├── financial_ratios.py
│   │   └── scoring.py                # [NEW] 乘法打分
│   ├── reporter/ (renderer+templates)
│   ├── rules/ (loader/validator/injector)
│   ├── llm/ (provider/manager/schema/cache/prompt_builder)
│   └── agents/ (context+coordinator+checkpoint+2Agents)
├── tests/ (unit/integration/functional)
├── .github/workflows/ci.yaml
├── docs/ (ARCHITECTURE/DATA_SCHEMA/TURTLE_STRATEGY/TESTING_GUIDE)
└── examples/quick_start.py
```

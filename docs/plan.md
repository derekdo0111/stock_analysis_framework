## 产品概述

在 `D:\project\stock-analysis-framework\` 创建 Python 股票分析框架，融合 **龟龟投资策略框架（Turtle Strategy v0.15）** 完整方法论——从 HardGate 一票否决、L2 分层初筛、公司分类、统一精算穿透回报率计算到乘法打分模型，实现从选股到报告生成的完整分析管线。系统采用确定性计算与 LLM 智能分析分离的架构，以 **Tushare（2000积分会员）** 为主要数据源，覆盖 **22 个接口**（8 财报 + 6 行情 + 8 股东治理）+ 行业数据，辅以 Web 搜索，通过 2 个 LLM Agent（分析+验证）配合 Jinja2 模板渲染输出 HTML+MD 格式的股票分析报告。

## 核心功能

### 选股器：HardGate 否决 + L2 分层初筛 + 公司分类 + 股票池

- **HardGate（龟龟因子一A）**：6项一票否决，仅用3个轻量Tushare接口（fina_audit、stock_basic、daily_basic），任何一项触发直接丢弃，不取全量数据。审计意见异常、频繁更换审计师、看不懂（人工黑名单）、上市未满5年、ST/*ST、短期暴涨暴跌（近60日 >150% 或 <-60%）
- **L2 初筛（20分）**：HardGate通过后批量拉取 fina_indicator（1次API调用）。维度：财务质量9pt（ROE 3+毛利率 2+资产负债率 2+经营现金流/净利润 2）+ 估值合理性6pt（PE 3+PB 2+PS 1）+ 流动性健康3pt（股息率 2+日均换手率 1）+ 加分项2pt（沪深港通+1，上市>10年+1）。硬门控：ROE<5%、PE<0、股息率=0直接淘汰。≥12候选池拉全量22接口，8~11观察池，<8淘汰
- **公司分类**：STANDARD_CONSUMER（消费/医药/公用）、HOLDING_COMPANY（控股型）→ 进入龟龟策略完整管线。CYCLICAL（强周期）、FINANCIAL（金融类）、GROWTH_NO_DIVIDEND（成长不分配）→ 分类阶段直接排除，理由：强周期利润波动剧烈穿透回报率失真、金融类CAPEX概念不适用、无分红则安全边际模型失效

### 乘法打分模型

Final Score = (L2初筛 20pt + L4穿透回报率 40pt + L5安全边际 25pt) × L3商业模式乘数（优×1.2/良×1.0/中×0.8/差截断）。L4统一精算：OE=经营CF净额−总CAPEX×维持系数(5年中位数)，PR≥12%→20分/≥8%→15分/≥5%→10分/<5%→0分，OE质量标签前置(可信/存疑×0.7/不可靠→0)，质量五级验证扣分后≤40分上限。≥75核心池，55~74观察池，<55备选池

### 龟龟策略核心指标

**Owners' Earnings（双路径计算）**：路径B(主)=经营性现金流净额−总CAPEX×维持系数(5年中位数，用于PR计算)；路径A(辅)=净利润+折旧摊销+减值损失−维持CAPEX(用于利润→现金转化率验证)。维持性CAPEX系数采用三因子评估法：行业先验(权重40%)×资产轻重评分(权重60%)。

**统一精算穿透回报率**：PR = OE_cf中位数(5年)/市值。三级阈值起点分(12%/8%/5%)，OE质量三级标签前置(🟢可信/🟡存疑×0.7/🔴不可靠→L4=0)，OE质量五级验证扣分(含金量+稳定性+趋势+BS一致性+利润→现金转化率)，上限40分。

**安全边际+仓位矩阵(L5 25分)**：外推可行度(6维0-30分：营收稳定性+利润率稳定性+ROE稳定性+行业可预测性+管理层稳定性+OE增长趋势)→分高/中/低三档；价值陷阱风险(5项+负债子触发，最多7分：盈利真实性+资产质量+负债压力(含高杠杆+利息覆盖)+行业趋势+治理风险)→分低/中/高风险。3×3仓位矩阵：高可行×低风险→15%，中可行×中风险→5%，低可行×高风险→0%。L5得分=(仓位上限%/15%)×25。

**SOTP双轨**：口径A=母公司可支配现金÷市值，口径B=合并口径×分红回流率÷市值，|A-B|>2pp→Agent综合判断。

**分红率**：Tushare dividend接口，5年中位数，≥50%验证可持续性，<20%安全边际打7折。

### 数据获取与存储

Tushare 22接口（8财报+6行情+8股东）多Adapter编排器并行+tenacity重试；19 Pydantic v2模型双轨Schema（核心字段+RawTushareData全量）；JSON+Parquet双格式存储

### LLM 智能层

**分析Agent**（CFA持证人·价值投资分析师，15年A股经验）：因子一B 9模块定性分析，每个结论使用三段式证据链格式（【数据】→【比较】→【结论】），temperature=0，Pydantic硬校验输出，最多3次retry后降级Python默认打分。

**验证Agent**（CPA+CFE·前四大审计经理，10年审计+3年FDD经验）：10项审计程序（MD&A兑现率+财务勾稽+行业横向对比+应收/存货/关联交易/商誉+分红可持续性+事实核查+内部一致性），验证通过的条目也必须在报告中标记✓并列出验证依据，不通过条目标记✗并列出矛盾点。

**SharedContext三层**（Immutable→Enriched→Opinion），Jinja2 HTML+MD双格式报告，报告中对分析Agent每个结论标注验证结果（🟢✓通过/🟡✗WARNING/🔴✗CRITICAL）。

## 技术栈

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


开发依赖：pytest, pytest-cov, ruff, mypy(strict), pre-commit, jupyter, openpyxl

## 实施策略

四阶段递进，先确定性层（Python），后智能层（LLM），每阶段产出可测试最小单元。

- **阶段一（地基）**：项目骨架+基础设施层+19 Pydantic Schema+数据校验存储+3规则YAML
- **阶段二（确定性管线）**：HardGate+L2初筛分类+Tushare 22接口+数据池转换+策略注册表+龟龟6子模块+通用比率+乘法打分+报告渲染+集成测试
- **阶段三（LLM智能层）**：Rules加载注入+LLM基础设施+SharedContext+分析Agent+验证Agent+Agent管线集成测试
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
│   ├── hard_gate_rules.yaml          # HardGate 6项否决配置
│   ├── l2_screener_rules.yaml        # L2 初筛指标+阈值+权重+分类排除
│   ├── turtle_constants.yaml         # 龟龟策略参数（OE/CAPEX系数/安全边际/仓位矩阵）
│   ├── agent_constraints.yaml        # 双Agent四层约束+证据链追踪+打分量表
│   └── ...
├── data_snapshots/
├── src/
│   ├── utils/ (exceptions/logger/retry/config/constants/validators)
│   ├── data_pool/ (schema/validator/storage/transformer)
│   ├── data_fetcher/ (base+3Adapter+web+orchestrator)
│   ├── screener/
│   │   ├── hard_gate.py              # 6项一票否决（3轻量接口）
│   │   ├── l2_screener.py            # L2 初筛（fina_indicator批量）
│   │   ├── classifier.py             # 公司分类（STANDARD/HOLDING进入，CYCLICAL/FINANCIAL/GROWTH排除）
│   │   └── stock_pool.py             # 股票池管理（核心/观察/备选）
│   ├── calculator/
│   │   ├── registry.py               # 策略注册表
│   │   ├── turtle_strategy/
│   │   │   ├── owners_earnings.py    # OE计算+CAPEX资产轻重评估
│   │   │   ├── penet_return.py       # 双轨穿透回报率+HH偏差+OE质量扣分
│   │   │   ├── cash_recon.py         # OE质量四级验证（含金量/稳定性/趋势/BS一致性）
│   │   │   ├── sotp_adjust.py        # SOTP双口径调整
│   │   │   ├── margin_safety.py      # 安全边际+3×3仓位矩阵+价值陷阱5项排查
│   │   │   └── constants_turtle.py   # 龟龟专用常数
│   │   ├── financial_ratios.py       # 通用比率（杜邦/CAGR/分位）
│   │   └── scoring.py                # 乘法打分 (L2+L4+L5)×L3
│   ├── reporter/ (renderer+templates)
│   ├── rules/ (loader/validator/injector)
│   ├── llm/ (provider/manager/schema/cache/prompt_builder)
│   └── agents/ (context+coordinator+checkpoint+2Agents)
├── tests/
│   ├── unit/
│   ├── integration/
│   └── functional/
├── .github/workflows/ci.yaml
├── docs/ (ARCHITECTURE/DATA_SCHEMA/TURTLE_STRATEGY/TESTING_GUIDE)
└── examples/quick_start.py
```

### SubAgent

- **code-explorer**
- 用途：在阶段实施过程中探索现有代码库结构，定位需要修改或引用的文件路径
- 预期结果：确保新模块导入路径正确，与已有代码风格一致

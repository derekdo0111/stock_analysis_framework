## 产品概述

在 `D:\project\stock-analysis-framework\` 创建 Python 股票分析框架，融合 **龟龟投资策略框架（Turtle Strategy v0.26）** 完整方法论——从 HardGate 一票否决、L2 纯门控初筛、公司分类、L3 十二维商业模式评估、L4 穿透回报率计算、L5 纯估值安全边际到加法百分制打分模型，然后通过财报深度分析（7模块纯Python）提取结构化洞察，与管线得分合并送入 LLM 进行商业知识检索+三维交叉验证（管线得分 vs 财报洞察 vs LLM知识），最终输出含验证结论的 HTML 报告。系统采用确定性计算与 LLM 智能分析分离的架构，以 **Tushare（2000积分会员）** 为主要数据源，覆盖 **22 个接口**（8 财报 + 6 行情 + 8 股东治理）+ 行业数据，通过 3 个 LLM Agent（分析+验证+交叉验证）配合 Jinja2 模板渲染输出 HTML 格式的股票分析报告。

## 核心功能

### 选股器：HardGate 否决 + L2 纯门控初筛 + 公司分类

- **HardGate（L1 一票否决）**：6项一票否决，仅用3个轻量Tushare接口（fina_audit、stock_basic、daily_basic），任何一项触发直接丢弃。审计意见异常、频繁更换审计师、看不懂（人工黑名单）、上市未满5年、ST/*ST、短期暴涨暴跌（近60日 >150% 或 <-60%）
- **L2 初筛（纯门控）**：v0.23 L2 降级为纯过滤器，不参与最终评分。HardGate通过后批量拉取 fina_indicator（1次API调用）。维度：财务质量9pt + 估值合理性6pt + 流动性健康3pt + 加分项2pt。硬门控：ROE<5%、PE<0、股息率=0直接淘汰。
- **公司分类**：STANDARD_CONSUMER（消费/医药/公用）、HOLDING_COMPANY（控股型）→ 进入龟龟策略完整管线。CYCLICAL（强周期）、FINANCIAL（金融类）、GROWTH_NO_DIVIDEND（成长不分配）→ 分类阶段直接排除。

### 加法百分制打分模型（v0.23）

```
Final = L3商业模式(30pt) + L4穿透回报率(45pt) + L5安全边际(25pt) = 100pt
```

**L3 商业模式（0-30分）**：十二维评估，每维 0-2 分，满分 24 → 映射到 30 分。

- **盈利能力（5维）**：ROE水平 + ROE稳定性(CV) + ROIC-ROE差距 + 毛利率水平 + 毛利率稳定性(CV)
- **成熟度（3维）**：CAPEX/经营CF比率 + 总资产CAGR + 营收CAGR
- **资本纪律（2维）**：分红持续性(每年≥30%+均值≥40%) + 股本变动(不摊薄)
- **治理（2维）**：管理层稳定性 + 盈利真实性(CF/NP≥0.6)

等级：优(20-24) / 良(14-19) / 中(8-13) / 差(0-7)

**L4 穿透回报率（0-45分）**：PR = (可支配现金 × 分配比率 + 回购注销) / 当前市值。

- 可支配现金 = 经营CF − 维持性CAPEX − 并购子公司 − 参股净增 − 财务费用 + 货币资金 − 限制性货币 − 短期借款 + 交易性金融资产
- 分配比率：一档(公告分红承诺) / 二档(mean(历史分红/净利润)算术平均)
- 三级阈值起点分：PR≥12%→20, ≥8%→15, ≥5%→10, <5%→0
- OE质量标签前置（可信/存疑×0.7/不可靠→L4=0），四级验证扣分（含金量+稳定性+趋势+BS一致性）
- 内部满分40，缩放到45（×45/40）

**L5 估值安全边际（0-25分）**：

- 估值安全边际率（0-15分）：合理市值 = (DC×分配比率+回购)/折现率7%, 安全边际率 = (合理市值-当前市值)/当前市值。≥50%→15, 30-50%→12, 15-30%→8, 0-15%→4, <0%→0
- 下行风险缓冲（0-5分）：资产底价(清算支撑)+股息托底+回购支撑
- 仓位矩阵（0-5分）：安全边际率≥30%→15%仓位, 15-30%→10%, 0-15%→5%, <0%→0%

**分池阈值**：≥75 核心池 / 50-74 观察池 / <50 备选池

**折现率**：7% = max(无风险利率+2%, 5%) + 个股风险溢价2%

### 龟龟策略核心指标

**Owners' Earnings（路径B）**：OE_cf = 经营性现金流净额 − 总CAPEX × 维持系数(5年中位数)。维持性CAPEX系数采用三因子评估法：行业先验(权重40%) + 资产轻重评分(权重60%)。

**穿透回报率（v0.22起）**：PR 直接反映数学真实回报，去除安全边际系数(×0.7/0.8)和红利税折扣(×0.9)。分配比率二档改为 mean(分红/净利润) 消除循环依赖。

**SOTP双轨**：口径A=母公司可支配现金÷市值，口径B=合并口径×分红回流率÷市值，|A-B|>2pp→Agent综合判断。

**分红率**：Tushare dividend接口，5年中位数，≥50%验证可持续性，<20%标记低分红。

### 数据获取与存储

Tushare 核心接口 + akshare 备用 + **财报深度分析**（7模块纯Python）+ **LLM 商业知识检索**（API→降级规则引擎）+ Web+LLM 提取（Layer3）→ 多源编排器 + tenacity重试；Pydantic v2 Schema双轨模型；JSON+Parquet双格式存储；数据通过 StockDataBundle 统一注入，所有计算模块只读 bundle。

### LLM 智能层

**分析Agent**（CFA持证人·价值投资分析师）：9模块定性分析，三段式证据链（【数据】→【比较】→【结论】），temperature=0，Pydantic硬校验，3次retry后降级。

**验证Agent**（CPA+CFE·前四大审计经理）：10项审计程序（MD&A兑现率+财务勾稽+行业横向对比+应收/存货/关联交易/商誉+分红可持续性+事实核查+内部一致性）。

**交叉验证Agent（v0.25 重写）**：接收管线得分 + 财报深度分析洞察，同时调用 LLM 训练知识进行商业判断，三维交叉验证（管线得分 vs 财报洞察 vs LLM知识），标注不一致项并给出修正建议。

### 财报深度分析 + LLM 商业知识检索与交叉验证管线（v0.25 重写）

```
Phase 1: Tushare 数据快照（22接口）
Phase 2: L2-L5 量化打分 → FinalScore(100分制)
Phase 3: 财报深度分析 → 7模块纯Python，从Tushare数据提取结构化洞察
Phase 4: LLM 商业知识检索 + 三维交叉验证（管线得分 vs 财报洞察 vs LLM知识）
Phase 5: brief.md 组装（Tushare数据 + 管线得分 + 财报洞察 + 交叉验证结果）
Phase 6: HTML 报告（含交叉验证结论）
```

**财报深度分析 7 模块**（纯 Python，从 Tushare 三大报表提取）：
1. 收入利润趋势：营收/净利润 CAGR + 增长稳定性
2. 利润率拆解：毛利率→营业利润率→净利率 逐年变化 + 趋势方向
3. ROE 杜邦拆解：ROE = 净利率 × 资产周转率 × 权益乘数，逐年展开
4. 现金流质量：经营CF/净利润比率、自由现金流、CAPEX负担率
5. 资产负债健康度：有息负债率、货币资金覆盖率、流动比率趋势
6. 分红政策：分红率趋势、分红连续性、每股分红CAGR
7. 营运效率：应收/应付/存货周转天数趋势

**LLM 商业知识检索 5 类**（LLM 基于训练数据回答）：
1. 商业模式与护城河：核心业务、盈利模式、竞争优势
2. 管理层与治理：管理层背景、股权结构、治理评价
3. 行业地位：行业排名、市场份额、竞争格局
4. 风险与监管：已知风险、监管问询、诉讼、财务争议
5. 分红与回购：分红政策、股东回报历史、回购公告

**降级链**：API LLM 可用 → 直接调用 DeepSeek；不可用 → Python 降级规则引擎（财报洞察 vs 管线得分简单对比），提示"请配置 DEEPSEEK_API_KEY"。

**brief.md 数据底稿结构**：
- 一、Tushare 原始数据（三大报表 / 财务指标 / 估值 / 分红）
- 二、管线计算得分（L2 / L3十二维 / L4逐步 / L5安全边际）
- 三、财报深度分析洞察（7模块结构化输出）
- 四、交叉验证结果（三维对比结论）

## 技术栈

| 类别 | 库 | 用途 |
| --- | --- | --- |
| 语言 | Python 3.11+ | 运行环境 |
| 包管理 | Poetry | 依赖管理与虚拟环境 |
| 数据模型 | Pydantic v2 | Schema + LLM输出 + SharedContext |
| 数据处理 | pandas, numpy | 财务数据处理与指标计算 |
| 模板引擎 | Jinja2 | HTML 报告渲染 |
| 配置 | PyYAML, python-dotenv | 规则加载+环境变量 |
| 日志 | loguru | 结构化日志 |
| 重试 | tenacity | 数据获取与LLM调用重试 |
| 可视化 | matplotlib, plotly | 图表生成 |
| LLM | openai, anthropic | 多 Provider 适配 |
| 数据源 | tushare | A股数据（2000积分） |
| 存储 | pyarrow | Parquet 列式存储 |

开发依赖：pytest, pytest-cov, ruff, mypy(strict), pre-commit, jupyter, openpyxl

## 实施策略

六阶段递进，先确定性层（Python），后智能层（LLM），每阶段产出可测试最小单元。

- **阶段一（地基）✅**：项目骨架+基础设施层+Pydantic Schema+数据校验存储+3规则YAML
- **阶段二（确定性管线）✅**：HardGate+L2门控+公司分类+L3十二维+OE+穿透回报率+L5纯估值+加法百分制+报告渲染
- **阶段三（LLM智能层）✅**：LLM基础设施+分析Agent+验证Agent+Agent管线+交叉验证Agent (v0.24)
- **阶段四（质量加固）✅**：端到端测试+CI配置+项目文档+examples
- **阶段五（回测验证）🟡**：Walk-Forward滚动窗口 → 分红验证 → PR兑现率+超额收益
- **阶段六（财报深度分析+交叉验证）🟡 进行中**：7模块财报深度分析 + LLM 商业知识检索 + 三维交叉验证 + brief.md 组装 + 含验证结论的HTML报告

## 目录结构

```
D:\project\stock-analysis-framework\
├── pyproject.toml
├── Makefile
├── README.md
├── CONTRIBUTING.md
├── PROJECT_STATUS.md
├── ISSUES.md
├── CHANGELOG.md
├── TRACEABILITY.md
├── rules/
│   ├── hard_gate_rules.yaml
│   ├── l2_screener_rules.yaml
│   ├── turtle_constants.yaml
│   └── agent_constraints.yaml
├── src/
│   ├── utils/
│   ├── data_pool/ (schema/validator/storage/transformer/bundle)
│   ├── data_fetcher/ (tushare_client/web_extractor/orchestrator)
│   ├── screener/
│   │   ├── hard_gate.py
│   │   ├── l2_screener.py
│   │   ├── classifier.py
│   │   └── stock_pool.py
│   ├── calculator/
│   │   ├── registry.py
│   │   ├── turtle_strategy/
│   │   │   ├── l3_calculator.py        # v0.23: 十二维商业模式(0-30pt)
│   │   │   ├── oe_calculator.py        # OE路径B计算+CAPEX评估
│   │   │   ├── pr_calculator.py        # 穿透回报率(0-45pt)
│   │   │   ├── l5_calculator.py        # v0.23: 纯估值安全边际(0-25pt)
│   │   │   ├── scoring.py              # v0.23: 加法百分制打分
│   │   │   └── ...
│   │   └── financial_ratios.py
│   ├── reporter/ (report_generator+unit_converter+brief_builder+brief_md_builder+templates)
│   ├── rules/ (loader/injector)
│   ├── llm/ (client/orchestrator/...)
│   └── agents/ (context/coordinator/...)
├── tests/
│   ├── unit/
│   ├── integration/
│   └── functional/
├── docs/ (plan.md/ARCHITECTURE.md)
├── scripts/ (verify_traceability.py)
├── examples/
└── .github/workflows/ci.yaml
```

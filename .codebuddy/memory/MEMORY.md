# Long-term Memory

## Project Conventions

### ⛔ 开发工作流：文档先行，代码后行（2026-06-03 确立）

任何改动必须在写代码之前先更新对应的项目管理文件。改动分三级：
- **Hotfix** (修bug)：跳过 plan.md 全部 + P2 除 CHANGELOG
- **Minor** (小优化)：跳过 plan.md + README.md
- **Major** (新功能/重构)：全流程 6 阶段

**6 阶段流程**：
1. **阶段〇（准备）**：阅读 TRACEABILITY.md + plan.md + PROJECT_STATUS.md，跑 verify_traceability.py 确认基线
2. **阶段一（设计）**：docs/plan.md → TRACEABILITY.md → pyproject.toml → verify_traceability.py ITEMS
3. **阶段二（元数据）**：PROJECT_STATUS.md → CHANGELOG.md → README.md → ISSUES.md
4. **阶段三（记忆）**：MEMORY.md + YYYY-MM-DD.md
5. **阶段四（实现）**：写代码 + 写测试
6. **阶段五（验证硬门控）**：ruff → mypy → pytest → verify_traceability.py（任一失败不得提交）
7. **阶段六（收尾）**：回溯 TRACEABILITY.md 状态（⚠️→✅）→ git add/commit/push

### ⛔ 版本号清单

每次版本升级必须更新以下 7 处：
1. `pyproject.toml` → version + description
2. `PROJECT_STATUS.md` → 当前版本
3. `CHANGELOG.md` → 新增版本条目
4. `README.md` → 标题版本号 + 阶段描述
5. `TRACEABILITY.md` → 最后更新日期 + 统计行版本号
6. `src/reporter/report_generator.py` → 模板页脚 + 管线标题
7. `src/cli.py` → print(f"[Turtle] v{version}")

### ⛔ TRACEABILITY.md 三列约定

| 列 | 含义 | ❌ | ⚠️ | ✅ | — |
|----|------|:--:|:--:|:--:|:--:|
| 实现 | 代码是否按设计完整实现 | 文件不存在 | 占位/空壳 | 完整实现 | |
| 连通 | 是否被生产代码 import | 零生产引用 | 仅测试引用 | 接入管线 | 实现❌时不适用 |
| 测试 | 是否有测试文件 | 无测试 | | 有test文件且>0函数 | 非代码项不适用 |

`verify_traceability.py` 自动检测连通和测试列（import 分析 + test 文件扫描），实现列需人工判定。

### ⛔ 铁律：每次写新代码前必须先跑 traceability

- **强制执行**：在写任何新代码之前，必须先运行 `python scripts/verify_traceability.py --only-failures`
- **补齐优先**：如果存在 ❌ 缺失项或 ⚠️ 未连通项，必须先补坑再开新坑
- **更新 TRACEABILITY.md**：如果新增了设计项，同步更新 `TRACEABILITY.md` 和 `scripts/verify_traceability.py` 中的 ITEMS 列表
- **退出码**：0=全部通过/1=有MISS/2=有WARN/3=两者都有
- 此规则于 2026-06-01 建立，2026-06-03 升级为完整6阶段工作流

### ⛔ 铁律：禁止编造任何数据
- **绝对禁止**凭记忆/印象/猜测编造数值。任何数字必须来自以下三种来源之一：
  1. 真实 API 调用结果（Tushare/Web等），且必须展示原始返回值
  2. 用户直接提供的数值
  3. 代码中的硬编码常量或 YAML 配置文件
- 在给用户展示数据表格时，**必须先调用对应 API** 获取真实数据，不可用"假设"凑数
- 如果 API 不可用，必须明确标注「此数据为估算/示例，非真实值」
- 用户于 2026-06-01 发现 agent 在解释回测流程时编造了茅台分红数据（实际应调用 Tushare dividend 接口获取），此为严重错误，写入铁律防止再犯

### ⛔ 铁律：实现前必须先输出改动清单（2026-06-03 确立）

- **触发条件**：任何以「实现一下」「开始写吧」「写代码」「动手吧」「干吧」等表达了「可以开始执行」语义的用户消息
- **强制动作**：在调用 write_to_file / replace_in_file 之前，必须先用纯文本输出一份改动清单，格式如：
  ```
  本次改动清单：
  新增 N 个文件: xxx.py, yyy.py, zzz.html
  修改 M 个文件: aaa.py (改xxx), bbb.py (改yyy)
  修改 K 个管理文件: plan.md, TRACEABILITY.md, verify_traceability.py, CHANGELOG.md, PROJECT_STATUS.md, MEMORY.md
  → 确认无误我开始写？
  ```
- **目的**：把「讨论语言」翻译成「执行清单」，防止跳过 plan → 实现之间的核对环节。管理文件是清单的一部分，不是事后的审计负担
- **例外**：hotfix（单文件修 bug）可以跳过清单直接写，但仍需事后补 CHANGELOG + 记忆文件
- 此规则于 2026-06-03 确认，针对 2026-06-03 简报功能开发中跳过 plan 直接写代码的问题

### 简报模板（2026-06-03 新增）
- `src/reporter/unit_converter.py` — 可配置单位转换层：`DATA_SOURCE["tushare"]` 定义字段→源单位映射，`to_yi()` 统一转为亿元
- `src/reporter/brief_builder.py` — `BriefBuilder(bundle, final_score)` 组装 context dict（区域A 4张数据趋势表 + 区域B 5张管线计算表）
- `src/reporter/templates/rich_brief.html` — Jinja2 深色主题简报模板
- CLI: `stock-analyze 600519.SH --brief` 生成 `brief_600519_SH.html`
- 三大报表字段 Tushare 返回"元"；daily_basic.total_mv 返回"万元"；fina_indicator 比率类返回"%"

### stock-analysis-framework (D:\project\stock-analysis-framework\)
- 龟龟投资策略 v0.26，Python 3.11+ / Pydantic v2 / Pandas / Tushare / Jinja2 / loguru / tenacity
- 阶段一~六完成，77 源文件 (~12700行)
- v0.26 修复: 取数粒度(年报过滤) + 列名(st_borr/trad_asset) + NaN防御(_safe_val) + 单位换算(万元→亿元) + 送转股排除
- v0.26 结果: 矛盾率 57%→40%，茅台营收CAGR -24.9%→6.9%，DC NaN→1075亿，PR NaN%→4.33%
- v0.25 新增: 7模块财报深度分析(纯Python) + LLM商业知识检索(合并交叉验证) + 三维对比(管线vs财报洞察vs LLM知识) + 删除DuckDuckGo
- v0.23 核心公式: **Final = L3(30pt) + L4(45pt) + L5(25pt) = 100pt** (加法百分制)
- L3: 十二维商业模式评估 (盈利能力5+成熟度3+资本纪律2+治理2), 每维0-2分, 满分24→30
- L4: 穿透回报率, 内部满分40缩放至45
- L5: 纯估值安全边际 (估值安全边际率15 + 下行缓冲5 + 仓位5), 折现率7%
- L2 降级为纯门控, 不参与最终评分
- 分池阈值: 核心≥75, 观察50-74, 备选<50
- GitHub: https://github.com/derekdo0111/stock_analysis_framework (main 分支)
- 新管线: Phase1(Tushare) → Phase2(打分) → Phase3(财报深度分析) → Phase4(LLM商业知识检索+交叉验证) → Phase5(brief.md) → Phase6(HTML报告)
- 财报深度分析: 7模块纯Python确定性计算, 从Tushare三大报表提取结构化洞察, v0.26修复年报过滤防止季/年报混算
- LLM 商业知识检索: LLM基于训练数据回答5类商业问题, 合并交叉验证为一次调用
- 降级链: API LLM → Python规则引擎（财报洞察 vs 管线得分简单对比）
- 核心理念：确定性计算(Python)与智能判断(LLM)彻底分离
- 所有规则存储在 YAML 中，代码不做硬编码阈值
- 数据双格式存储：JSON（可读调试）+ Parquet（高性能查询）
- 数据源四层架构：Tushare(主) → akshare(备用) → 财报深度分析(Python) → LLM商业知识(LLM) → 年报PDF(降级)

### Projects Location
- 所有项目统一放在 D:\project\ 下，不放在 C:\Users\harry\CodeBuddy\

### Keys
- 19 Pydantic v2 Schema 双轨设计（核心字段 + RawTushareData 全量）
- 3规则YAML驱动（hard_gate / l2_screener / turtle_constants）
- Agent约束：分析Agent(CFA)三段式证据链 + 验证Agent(CPA+CFE)10项审计程序
- 报告增强：每个分析结论标注验证结果（🟢✓/🟡✗WARNING/🔴✗CRITICAL）

## 方法论 v0.21 分配比率外推修正（2026-06-02）

### 问题
DC 公式包含年末 money_cap，该值已被当年分红抽走。外推分配比率时 `ratio = total_div / DC` 产生循环悖论：
- 分红越多 → money_cap 年末越小 → DC 越小 → ratio 虚高（早年可达 133%）

### 修正
`_extrapolate_from_history()` 中：`adjusted_dc = dc + total_div`（把分红加回年末现金），再用 `total_div / adjusted_dc` 算比率。
- ratio 天然 ≤ 100%，消除循环悖论
- 不需要另存年初 money_cap，不需要改 DC 公式

## 方法论 v0.20 DC maintenance_capex 修正（2026-06-02）
- DC 公式：`c_pay_acq_const_fiolta`（购建固定资产、无形资产）替代 `stot_out_inv_act`（投资活动现金流出总计）
- 只扣维持性 CAPEX，不再扣所有投资流出（含短期理财、参股等）

## 方法论 v0.19 PR 公式第三次修正（2026-06-01）

### PR = (可支配现金 × 分配比率 × 0.90 + 回购注销) / 当前市值

**v0.18 问题**：分子仍是历史分红，不前瞻。

**v0.19 修正**：
- **分子**：可支配现金 × 分配比率 × (1-红利税10%) + 回购注销金额
- **分母**：最新收盘总市值（`daily_basic.total_mv` 最新一条）

### 分配比率两级降级
| 优先级 | 来源 | 公式 |
|---|---|---|
| 一档 | 公告分红承诺（Web+LLM提取） | 承诺值 × 0.8（安全边际） |
| 二档 | 历史外推 | 5年中位数(分红/可支配现金) × 0.7 |

### OE 简化（v0.19）
- **删除路径A**（利润表视角 OE_income）：数据不可靠（折旧用CAPEX×0.55估计）
- **删除质量验证第5项**（利润→现金转化率）：输入不可靠则输出无意义
- **质量验证从5级→4级**
- **CAGR bug修复**：3个数据点→2个增长期间，`**(1/3)` → `**(1/2)`

### 新增模块
1. `src/data_fetcher/web_extractor.py` — Web+LLM 轻量提取（方案A，只做实体提取不做推理）
2. `src/data_pool/schema/disposable_cash.py` — 可支配现金计算器
3. `StockDataBundle` 新增3字段：`dividend_commitment`, `buyback_cancellation`, `restricted_cash`
4. `DataPoolOrchestrator._fetch_all()` 新增 Layer 3（Web搜索+LLM提取）

### 改动的文件
- **新增**: `web_extractor.py`, `disposable_cash.py`
- **重写**: `pr_calculator.py`（v0.19公式）
- **删减**: `oe_calculator.py`（删除路径A+验证5）
- **改造**: `bundle.py`, `orchestrator.py`, `scoring.py`, `cli.py`, `models.py`, `schemas.py`, `turtle_constants.yaml`
- **导出更新**: `data_pool/__init__.py`, `data_fetcher/__init__.py`

## 方法论 v0.18 关键设计决策（2026-06-01）

### PR 公式第二次根性修正：分母从「市值」改为「可支配现金」

**v0.17 公式**：`PR = (分红+回购) / 年末总市值` — 分母是市场定价，股价跌PR翻倍，本质是"市场先生的函数"

**v0.18 公式**：`PR = (分红+回购) / 真实可支配现金` — 分母是公司口袋里真正能花的钱，衡量管理层的「资本配置纪律」

```
真实可支配现金 = 经营CF净额(n_cashflow_act)           # Tushare: cashflow
               - 投资活动现金流出小计(stot_out_inv_act) # 所有投资支出全扣，成长性投入视为打水漂
               - 财务费用(fin_expense)                  # Tushare: income
               + 货币资金(money_cap)                    # Tushare: balancesheet
               - 限制性货币                             # ❌ Tushare无 → PDF年报提取
               - 短期借款(st_borr)                      # Tushare: balancesheet
               + 交易性金融资产(trad_asset)              # 短期理财视为现金等价物
```

**关键设计决策**：
- 不只用 CAPEX，而是减去所有投资活动现金流出（建厂+买设备+参股+并购），全部视为成长赌注
- 短期理财：在"投资流出"扣掉，通过末尾"+交易性金融资产"加回 → 净效果为零
- 参股/并购：进入长期股权投资，不被加回 → 永久扣掉
- 限制性货币：Tushare/akshare 均无此字段 → 用 download-annual-report skill 从年报 PDF 提取
- 时间错配：年初买年末到期的理财会被误扣（现金流全年累计 vs BS 年末快照），年末 money_cap 部分对冲

### 数据源策略

| 字段 | 主源 | 备用 |
|------|------|------|
| 经营CF/投资流出/CAPEX | Tushare cashflow | akshare |
| 货币资金/交易性金融资产/短期借款 | Tushare balancesheet | **年报 PDF 提取** |
| 财务费用 | Tushare income | akshare |
| 限制性货币 | **年报 PDF 提取** | 估算(0~3%) |
| 分红/回购 | Tushare dividend/repurchase | — |

- Tushare 字段名注意：`trad_asset`(非 tradable_fin_assets), `st_borr`(非 st_borrow)
- Tushare free tier 部分字段 NaN → PDF 降级
- 茅台 2025 验证：交易性金融资产=0（财务公司债投到期收回），限制性货币=74亿（法定准备金）
- CNINFO 巨潮资讯 API 已集成到 download-annual-report skill（SH 股票确认可用）

## 方法论 v0.15 关键设计决策（2026-06-01）

### 穿透回报率重构（v0.14 → v0.15 最大变更）

1. **双轨→单轨统一精算**：取消粗算(最新年OE)和精算(5年中位数)双轨，统一使用现金流路径OE的5年中位数
2. **HH偏差取消**：由OE稳定性(CV)替代，避免「今年异常差」被错误惩罚
3. **OE质量标签前置**：三级标签(🟢可信/🟡存疑×0.7/🔴不可靠→L4=0)在PR计算前生效，而非后置扣分
4. **OE双路径计算**：路径B(现金流，主)用于PR + 路径A(利润表，辅)用于「利润→现金转化率」验证
5. **OE质量五级验证**：含金量+稳定性+趋势+BS一致性+利润→现金转化率(新增)
6. **L5外推可行度6维**：新增OE增长趋势(近3年CAGR)。逆周期信号不纳入（与龟龟策略排除强周期股的逻辑冲突）
7. **价值陷阱第3项强化**：负债压力新增子触发(有息负债/EBITDA>4、EBIT/利息<3)
8. **PR三级阈值**：≥12%→20分, ≥8%→15分, ≥5%→10分, <5%→0分
9. **增长维度不融入PR**：PR保持静态快照纯粹性，增长通过L5外推可行度独立评估
10. **L3乘数不变**：保持 v0.14 的 ×1.2/×1.0/×0.8/reject

### 设计哲学

- 穿透回报率 = 静态快照：「以当前市值买入，当前经营能力带来的回报率」
- 增长的正确归宿是安全边际(L5)，不是PR本身
- 护城河问题通过L3乘数处理（×1.2/×1.0/×0.8），而非降低L4权重
- 负债问题通过价值陷阱排查统一处理，不在OE分子层面扣减（避免四次惩罚）

## 方法论 v0.14 关键设计决策（2026-05-31）

1. **公司分类精简**：CYCLICAL/FINANCIAL/GROWTH_NO_DIVIDEND 在分类阶段直接排除，不进入龟龟策略
2. **现金视角从资产负债表改为经营性现金流 OE 视角**：OE = 经营CF净额 − 维持性CAPEX
3. **维持性CAPEX系数改为三因子评估法**：行业先验(40%) + 资产轻重评分(60%，CAPEX/营收+固定资产周转率+折旧/营收)
4. **OE质量四级验证**替代旧版资产负债表现金扣减逻辑
5. **安全边际完整算法**：外推可行度5维评分 × 价值陷阱5项(含触发条件) → 3×3仓位矩阵
6. **分红率**：Tushare dividend接口，5年中位数，含可持续性验证
7. **agent_constraints.yaml**：双Agent四层约束体系（角色→行为边界→Rubric打分/审计程序→Schema硬校验）
8. **分析Agent**：CFA身份，三段式证据链（【数据】→【比较】→【结论】），每个结论必须有证据
9. **验证Agent**：CPA+CFE审计师，10项审计程序，通过项也标记✓+验证依据，不通过项标记✗+矛盾点
10. **报告增强**：每个分析结论旁标注验证结果（🟢✓/🟡✗WARNING/🔴✗CRITICAL）

## 测试策略（2026-06-01）

### 三层测试金字塔
- **单元测试** tests/unit/：隔离、无外部依赖，mock 所有网络调用，毫秒级。阶段一开始写，贯穿全程
- **集成测试** tests/integration/：模块间串联，使用 fixture 模拟数据，秒级。阶段二+阶段三写
- **功能/E2E测试** tests/functional/：全管线端到端（选股→数据→计算→Agent→报告），分钟级。阶段四写

### 工具栈
- pytest ≥7.4 + pytest-cov ≥4.1（覆盖率目标 ≥80%）
- ruff ≥0.1（lint）+ mypy ≥1.5（strict=true 类型检查）
- CI/CD：GitHub Actions（阶段四配置），Pylint → mypy → 单元→集成→E2E 流水线

### 质量门禁
- ruff check src/ tests/ 零错误
- mypy src/ 通过
- pytest --cov=src --cov-report=html 覆盖率 ≥80%

### LLM 测试策略
- Agent 单元测试使用 mock LLM 响应（预制 JSON）
- 只校验 Pydantic 输出 Schema，不测试 LLM 的"智能"
- 集成测试验证 Agent 重试→降级逻辑（3次失败后回退 Python 默认打分）

### Fixture 设计
- 使用 dataclass（StockProfile），IDE 自动补全，类型安全
- 10 个测试剖面覆盖所有代码路径：PERFECT/GOOD/MID/POOR（4档质量）+ HOLDING/UTILITY（2类特殊）+ BANK/CYCLIC/GROWTH_NODIV（3类排除）+ ST_STOCK（否决）
- 每个剖面包含完整伪 Tushare 数据 + 预期值（expected_l2_score, expected_pr, expected_final_score 等）
- session 级加载规则 YAML + 全部剖面数据，测试间共享复用
- mock_tushare_adapter 通过 monkeypatch 注入，完全隔离网络

### 快照回归
- 功能测试使用预计算"金标准"结果对比，防止重构改变核心计算逻辑
- 数值容差：OE_cf 中位数 <0.01, PR <0.001, Final Score <0.1

## 阶段五：回测验证（2026-06-01 设计定型）

### 核心哲学
- **只验证分红，不碰股价**：PR 的含义是「以当前市价买入后每年能拿回多少可分配现金」，分红是唯一兑现形式
- **对比基准：无风险利率（国债收益率）**，非沪深300 —— 股价涨跌是市场情绪，拿它做裁判等于把策略交给别人
- **留存收益不纳入验证**：留存价值增长是增长维度的事，增长由 L5 独立处理，不应混入 PR 验证
- **回测模块站在管线之外验证管线**：不是管线的一部分，而是对管线产出的独立审计

### 验证公式
```
一条公式，一个比较：
  PR → 预期每年每股可分配现金
       ↓
  实际每年每股分红（Tushare dividend 接口）
       ↓
  比较：股息回报 vs 同期无风险利率
```

### 两个核心指标
1. **PR 兑现率** = 实际股息回报 / 预期 PR → ≥0.7 为 PR 预测合格
2. **超额** = 股息回报 − 无风险利率 → >0 为策略有效

### Walk-Forward 窗口
- 5年数据选股 → N年持有验证 → 窗口滑动
- 示例：2015-2020 数据选股 → 2021-2025 分红验证

### 分组统计
- 按 Final Score 排名分组，对比 Top 5 vs Bottom 5 的股息回报差
- 跨窗口汇总：win_rate（股息>无风险利率的股票占比）、PR 兑现率中位数

### 模块结构
```
src/backtest/
├── window_manager.py      # 滚动窗口定义
├── pipeline_runner.py     # 每窗口跑完整管线 → PR + Final Score
├── dividend_validator.py  # 计算实际分红回报 + PR兑现率
├── statistics.py          # win_rate / PR兑现率 / 分组spread
└── report.py              # 对比基准：无风险利率
```

## 项目结构关键路径

- 规则配置：rules/hard_gate_rules.yaml, rules/l2_screener_rules.yaml, rules/turtle_constants.yaml, rules/agent_constraints.yaml
- 筛选器：src/screener/ (hard_gate.py, l2_screener.py, classifier.py, stock_pool.py)
- 计算引擎：src/calculator/ (registry.py, turtle_strategy/, financial_ratios.py, scoring.py)
- LLM Agent：src/agents/agents/ (analysis_agent.py, validate_agent.py)
- 数据池：src/data_pool/ (schema.py 19模型, validator.py, storage.py, transformer.py, bundle.py)

## 数据池架构改革（2026-06-01 强制执行）

**原则**：只有 `DataPoolOrchestrator._fetch_all()` 有权直连 Tushare，其他所有模块只能从 `StockDataBundle` 读数据。

**架构**：
```
CLI → DataPoolOrchestrator.snapshot_stock() → JSON/Parquet 缓存 → (唯一调用 Tushare 的入口)
CLI → orchestrator.get_bundle() → StockDataBundle (纯读缓存)
CLI → TurtleScorer(bundle) → 7 个子模块全部从 bundle 读
```

**改造的 11 个文件**：
- 新增: `src/data_pool/bundle.py` (StockDataBundle dataclass)
- 改造: `src/data_fetcher/orchestrator.py` (新增 get_bundle(), 修复 repurchase 拉取)
- 改造: `src/screener/hard_gate.py`, `l2_screener.py`, `classifier.py`
- 改造: `src/calculator/turtle_strategy/oe_calculator.py`, `pr_calculator.py`, `l5_calculator.py`, `scoring.py`
- 改造: `src/cli.py`, `src/backtest/pipeline_runner.py`, `src/backtest/dividend_validator.py`
- 改造: `src/data_pool/__init__.py` (导出 StockDataBundle)

结果：追溯 21/21=100%连通，零 lint 错误，全部模块 import 通过。
- 测试：tests/unit/, tests/integration/, tests/functional/

## download-annual-report Skill（2026-06-01 升级）

位置：`~/.codebuddy/skills/download-annual-report/`

**三级降级链**：
1. CNINFO 巨潮资讯 API（官方）→ SH 股票确认可用，SZ 股票 orgId 待确定
2. 中商情报网 (s.askci.com) → 抓取 10jqka CDN 链接
3. Xueqiu 雪球 → URL 猜测

**CNINFO API 关键参数**：`column="szse"`, `plate="sse,sse"`, `category="category_ndbg_szsh;category_ndbg_sse"`
- PDF URL 格式：`http://static.cninfo.com.cn/finalpage/{YYYY-MM-DD}/{id}.PDF`

**PDF 解析**：pdfplumber 直接提取文本，搜索关键词（交易性金融资产、受限的货币资金等），用于填补 Tushare/akshare 的字段缺失

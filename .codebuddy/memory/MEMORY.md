# Long-term Memory

## Project Conventions

### stock-analysis-framework (D:\project\stock-analysis-framework\)
- 龟龟投资策略 v0.15，Python 3.9+ / Poetry / Pydantic v2 / Pandas / Tushare / Jinja2 / loguru / tenacity / openai+anthropic
- 4阶段9todo开发，当前阶段五（回测验证）待开工
- GitHub: https://github.com/derekdo0111/stock_analysis_framework (main 分支)
- 核心理念：确定性计算(Python)与智能判断(LLM)彻底分离
- 所有规则存储在 YAML 中，代码不做硬编码阈值
- 数据双格式存储：JSON（可读调试）+ Parquet（高性能查询）

### Projects Location
- 所有项目统一放在 D:\project\ 下，不放在 C:\Users\harry\CodeBuddy\

### Keys
- 19 Pydantic v2 Schema 双轨设计（核心字段 + RawTushareData 全量）
- 3规则YAML驱动（hard_gate / l2_screener / turtle_constants）
- Agent约束：分析Agent(CFA)三段式证据链 + 验证Agent(CPA+CFE)10项审计程序
- 报告增强：每个分析结论标注验证结果（🟢✓/🟡✗WARNING/🔴✗CRITICAL）

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
- 数据池：src/data_pool/ (schema.py 19模型, validator.py, storage.py, transformer.py)
- 测试：tests/unit/, tests/integration/, tests/functional/

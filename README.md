# Stock Analysis Framework — 龟龟投资策略 v0.19

融合龟龟投资策略完整方法论的 A 股量化分析框架，从选股到报告生成的全管线。

> GitHub: https://github.com/derekdo0111/stock_analysis_framework

## 架构概览

```
选股器(HardGate→L2初筛→分类→股票池)
   → 数据池(Tushare 22接口→Schema→存储)
      → 计算引擎(龟龟6子模块→乘法打分)
         → LLM智能层(双Agent分析)
            → 报告渲染(HTML+MD)

回测验证（阶段五）—— 站在管线之外独立审计：
   PR → 预期分红 → 实际分红 vs 无风险利率
```

## 五阶段实施

1. **阶段一（地基）✅**：Pydantic v2 Schema + YAML加载器 + Tushare适配器(22接口) + 19数据模型 + JSON/Parquet存储
2. **阶段二（确定性管线）✅**：HardGate(6项否决) + L2初筛(20分) + 公司5分类 + OE路径B + 穿透回报率(v0.19前瞻公式) + L5安全边际 + 乘法打分
3. **阶段三（LLM智能层）✅**：DeepSeek/OpenAI/Anthropic客户端 + CFA分析Agent(9模块Rubric+三段式证据链) + CPA+CFE审计Agent(10项审计程序) + Jinja2报告 + CLI
4. **阶段四（质量加固）✅**：162测试 + ruff/mypy零错误 + 全链路茅台验证
5. **阶段五（回测验证）🟡**：Walk-Forward 滚动窗口 → 分红验证 → PR兑现率 + 超额收益 —— 代码完成，待真数据回测

## 快速开始

```bash
# 安装
pip install -r requirements.txt  # 或 poetry install

# 配置环境变量 (.env)
TUSHARE_TOKEN=your_tushare_token
DEEPSEEK_API_KEY=your_deepseek_key  # 可选, LLM Agent

# 分析股票
python -m src.cli 600519.SH --html
# 安装依赖
poetry install

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 Tushare Token、OpenAI/Anthropic API Key

# 运行
poetry run stock-analyze
```

## 项目结构

参见 `docs/plan.md`

## 开发

```bash
make lint       # 代码检查
make typecheck  # 类型检查
make test       # 运行测试
make test-cov   # 测试覆盖率
```

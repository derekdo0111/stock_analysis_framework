# Stock Analysis Framework — 龟龟投资策略 v0.13

融合龟龟投资策略完整方法论的 A 股量化分析框架，从选股到报告生成的全管线。

## 架构概览

```
选股器(HardGate→L2初筛→分类→股票池)
   → 数据池(Tushare 22接口→Schema→存储)
      → 计算引擎(龟龟6子模块→乘法打分)
         → LLM智能层(双Agent分析)
            → 报告渲染(HTML+MD)
```

## 四阶段实施

1. **阶段一（地基）**：项目骨架 + 基础设施 + Pydantic Schema + 规则YAML
2. **阶段二（确定性管线）**：HardGate + L2初筛 + 数据获取 + 策略计算 + 报告
3. **阶段三（LLM智能层）**：双Agent + SharedContext + 智能分析
4. **阶段四（质量加固）**：CI + 文档 + examples

## 快速开始

```bash
# 安装依赖
poetry install

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 Tushare Token

# 运行
poetry run stock-analyze
```

## 项目结构

参见 `docs/ARCHITECTURE.md`

## 开发

```bash
make lint       # 代码检查
make typecheck  # 类型检查
make test       # 运行测试
make test-cov   # 测试覆盖率
```

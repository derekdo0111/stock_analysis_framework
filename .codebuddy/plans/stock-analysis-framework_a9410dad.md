---
name: stock-analysis-framework
overview: 在 D:\project\stock-analysis-framework\ 创建 Python 股票分析框架，融合龟龟策略——HardGate 否决、L2 多维初筛、乘法打分、双轨穿透回报率、公司分类注册表、SOTP 双轨估值，四阶段递进（地基→确定性管线→LLM智能→质量加固）。
todos:
  - id: phase1-scaffold
    content: 阶段一：创建项目骨架——pyproject.toml、Makefile、.pre-commit-config.yaml、.gitignore、.env.example、README.md、.codebuddyrules、.editorconfig、.vscode三件套、PROJECT_STATUS.md、ISSUES.md、CHANGELOG.md、notebooks/、全部src/和tests/子包目录结构，及新增rules/下hard_gate_rules.yaml/l2_screener_rules.yaml/turtle_constants.yaml三个规则配置文件
    status: pending
  - id: phase1-utils
    content: 阶段一：搭建基础设施层——src/utils/exceptions.py（5个自定义异常）、logger.py（loguru封装）、retry.py（tenacity封装）、config.py（pydantic-settings含TUSHARE_TOKEN）、constants.py（汇率/税率/无风险利率/门坎等全局参数）、validators.py，编写对应单元测试
    status: pending
    dependencies:
      - phase1-scaffold
  - id: phase1-data-pool-schema
    content: 阶段一：实现数据池核心——src/data_pool/schema.py（19个Pydantic模型+StockDataPackage聚合体）、validator.py（DataValidator完整度评分/审计意见检查/商誉预警）、storage.py（JSON+Parquet双格式存储），编写完整单元测试
    status: pending
    dependencies:
      - phase1-utils
  - id: phase2-hardgate
    content: 阶段二：实现HardGate否决器——src/screener/hard_gate.py（6项一票否决：审计异常/频繁换所/ST标记/上市未满5年/短期暴涨跌/人工黑名单，仅用3轻量接口，不合规直接标记排除不取全量），配置rules/hard_gate_rules.yaml，编写单元测试
    status: pending
    dependencies:
      - phase1-data-pool-schema
  - id: phase2-l2-classifier
    content: 阶段二：实现L2初筛与公司分类——src/screener/l2_screener.py（fina_indicator批量拉取，8指标+3硬门控+加分项，20分制，12分以上进候选池）、src/screener/classifier.py（5类自动分类：STANDARD/HOLDING/CYCLICAL/FINANCIAL/GROWTH_NO_DIV）、src/screener/stock_pool.py（核心/观察/备选股票池管理），配置rules/l2_screener_rules.yaml，编写单元测试
    status: pending
    dependencies:
      - phase2-hardgate
  - id: phase2-data-fetcher
    content: 阶段二：实现Tushare数据获取——src/data_fetcher/（base.py抽象基类、tushare_financial.py 8财报、tushare_market.py 6行情、tushare_holder.py 8股东、web_search.py、orchestrator.py并行编排器+tenacity重试+Tushare频率控制）
    status: pending
    dependencies:
      - phase1-data-pool-schema
  - id: phase2-pool-transformer
    content: 阶段二：实现数据池转换——src/data_pool/transformer.py（Tushare dict/DataFrame至Pydantic转换，双轨：核心字段至Schema+全量至RawTushareData）、pool_manager.py（fetch至transform至validate至store全流程）
    status: pending
    dependencies:
      - phase2-data-fetcher
      - phase1-data-pool-schema
  - id: phase2-calculator-registry
    content: 阶段二：实现策略注册表与龟龟指标——src/calculator/registry.py（StrategyRegistry按分类匹配管线）、src/calculator/turtle_strategy/（owners_earnings.py粗算穿透回报率含维持CAPEX系数表、penet_return.py双轨制含HH偏差扣分、cash_recon.py真实可支配现金重建、sotp_adjust.py控股公司双口径调整、margin_safety.py安全边际/仓位矩阵/价值陷阱5项排查、constants_turtle.py龟龟专用常数），配置rules/turtle_constants.yaml，编写单元测试
    status: pending
    dependencies:
      - phase1-data-pool-schema
  - id: phase2-financial-ratios
    content: 阶段二：实现通用比率与打分——src/calculator/financial_ratios.py（杜邦分解/现金流质量/CAGR/估值历史分位）、src/calculator/scoring.py（乘法打分：(L2+L4+L5)×L3乘数，≥75核心池/55-74观察池/
    status: pending
    dependencies:
      - phase2-calculator-registry
---

## 产品概述

在 `D:\project\stock-analysis-framework\` 创建 Python 股票分析框架，融合 **龟龟投资策略框架（Turtle Strategy v0.13）** 完整方法论——从 HardGate 一票否决、L2 分层初筛、公司分类、双轨穿透回报率计算到乘法打分模型，实现从选股到报告生成的完整分析管线。

## 核心功能

### 选股器：HardGate 否决 + L2 分层初筛 + 公司分类 + 股票池

- **HardGate**：6项一票否决，仅用3个轻量Tushare接口
- **L2 初筛（20分）**：8指标+3硬门控+加分项，≥12进候选池
- **公司分类**：STANDARD_CONSUMER / HOLDING_COMPANY / CYCLICAL / FINANCIAL / GROWTH_NO_DIVIDEND

### 计算引擎：龟龟策略 + 通用比率 + 策略注册表

- 策略注册表按分类匹配管线
- 龟龟指标：Owners' Earnings、双轨穿透回报率、真实可支配现金重建、SOTP双轨、安全边际+仓位矩阵
- 通用比率：杜邦分解、现金流质量、CAGR、估值分位

### 乘法打分模型

Final Score = (L2 20pt + L4穿透回报率 40pt + L5安全边际 25pt) × L3商业模式乘数

### LLM 智能层 + 报告生成

分析Agent + 验证Agent，SharedContext三层，Jinja2 HTML+MD报告。

## 实施策略

四阶段递进：地基→确定性管线→LLM智能层→质量加固

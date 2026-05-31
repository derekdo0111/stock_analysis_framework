# Changelog

## [Unreleased] v0.15

### Changed
- **穿透回报率重构**：双轨（粗算/精算）→ 统一精算单轨
  - OE 来源统一为现金流路径（经营CF−总CAPEX×维持系数）的5年中位数
  - 取消 HH 偏差扣分，由 OE 稳定性（CV）替代
  - PR 三级阈值：≥12%→20分, ≥8%→15分, ≥5%→10分, <5%→0分
- **OE 质量标签前置**：三级标签（🟢可信/🟡存疑×0.7/🔴不可靠→L4=0），在PR计算前生效
- **OE 双路径计算**：路径B(现金流，主)用于PR计算 + 路径A(利润表，辅)用于质量验证
- **OE 质量验证五级**：新增「利润→现金转化率」维度（路径B OE/路径A OE）

### Added
- **L5 外推可行度新增1维**：OE增长趋势(近3年CAGR)
- **价值陷阱第3项强化**：负债压力新增子触发（有息负债/EBITDA>4、EBIT/利息<3）


## [v0.14] - 2026-05-31

### Added
- 项目骨架初始化
- 3 规则 YAML (hard_gate, l2_screener, turtle_constants)
- pyproject.toml (Poetry 包管理)
- CI 配置 (GitHub Actions)

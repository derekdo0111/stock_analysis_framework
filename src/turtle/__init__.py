"""龟龟投资策略 — 完整 L2-L5 量化管线 + LLM 分析 + HTML 报告。

这是项目的第一个策略插件。

目录结构:
- turtle/cli.py: stock-analyze CLI 入口
- turtle/calculator/: L2-L5 计算引擎 (scoring, oe, pr, l3, l5, cash_recon, sotp)
- turtle/screening/: 全A筛选 (hard_gate, classifier, l2_screener, run_screener)
- turtle/llm/: 龟龟专属 LLM Agent (analysis, business_retrieval, cross_validation, orchestrator)
- turtle/reporter/: 报告生成 (brief.md, HTML 报告)
- turtle/rules/: YAML 规则 + Pydantic 模型 (hard_gate, l2, l3, l4, l5, agent_constraints)
"""

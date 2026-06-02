"""规则注入器 — 将 YAML 规则注入 LLM prompt 上下文。"""

from __future__ import annotations

from src.rules.schemas import RuleSet


class RuleInjector:
    """规则注入器：将 YAML 规则转为 LLM prompt 可用的结构化文本。

    用途:
    - 分析 Agent 需要知道打分 Rubric → 注入 agent_constraints 的分析模块
    - 验证 Agent 需要知道审计程序 → 注入 agent_constraints 的验证模块
    - OE/PR 计算需要常数 → 注入 turtle_constants
    """

    def __init__(self, rules: RuleSet):
        self._rules = rules

    def inject_for_analysis_agent(self) -> str:
        """为分析 Agent 构建规则上下文 prompt。"""
        parts = ["# 分析规则上下文\n"]

        agent_cfg = getattr(self._rules, 'agent_constraints', None)
        if agent_cfg is None:
            return ""

        # 分析模块 Rubric
        analysis = getattr(agent_cfg, 'analysis', None)
        if analysis:
            modules = getattr(analysis, 'modules', [])
            for mod in modules:
                name = getattr(mod, 'name', '')
                weight = getattr(mod, 'weight', 0)
                desc = getattr(mod, 'description', '')
                parts.append(f"## {name} (权重: {weight})")
                parts.append(f"{desc}\n")

        return "\n".join(parts)

    def inject_for_verification_agent(self) -> str:
        """为验证 Agent 构建审计程序上下文 prompt。"""
        parts = ["# 审计规则上下文\n"]

        agent_cfg = getattr(self._rules, 'agent_constraints', None)
        if agent_cfg is None:
            return ""

        verify = getattr(agent_cfg, 'verification', None)
        if verify:
            procedures = getattr(verify, 'procedures', [])
            for proc in procedures:
                name = getattr(proc, 'name', '')
                desc = getattr(proc, 'description', '')
                severity = getattr(proc, 'severity', '')
                parts.append(f"## {name} [{severity}]")
                parts.append(f"{desc}\n")

        return "\n".join(parts)

    def inject_turtle_constants(self) -> str:
        """将龟龟常数注入 prompt。"""
        tc = getattr(self._rules, 'turtle_constants', None)
        if tc is None:
            return ""

        parts = ["# 龟龟策略常数\n"]

        oe = getattr(tc, 'owners_earnings', None)
        if oe:
            capex = getattr(oe, 'maintenance_capex_coefficient', None)
            if capex:
                parts.append(f"- CAPEX 行业先验权重: {getattr(capex, 'prior_weight', 'N/A')}")
                parts.append(f"- CAPEX 资产轻重权重: {getattr(capex, 'asset_intensity_weight', 'N/A')}")

        pr = getattr(tc, 'penetration_return', None)
        if pr:
            parts.append(f"- PR 阈值: {getattr(pr, 'thresholds', [])}")
            parts.append(f"- PR 最大分: {getattr(pr, 'max_score', 'N/A')}")

        return "\n".join(parts)


__all__ = ["RuleInjector"]

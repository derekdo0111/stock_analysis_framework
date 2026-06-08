"""
v0.30: 结构化声明审计循环 — 声明类型定义。

数据模型:
- AnalysisClaim: 分析 Agent 从报告中提取的一条原子声明
- VerifiedClaim: CV Agent 核查后的声明
- RevisedClaim: 分析 Agent 面对 CV 反馈后的修正
- ClaimVerificationResult: 逐条核查汇总
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ══════════════════════════════════════════════════════════════
# Phase 5a.5 — 声明提取
# ══════════════════════════════════════════════════════════════


@dataclass
class AnalysisClaim:
    """分析 Agent 从完整报告中提取的一条可核查的原子声明。"""

    id: str                          # 声明编号，如 "claim_01"
    dimension: str                   # 所属维度，如 "护城河深度" / "穿透回报率"
    claim_text: str                  # 完整的声明文本
    claim_type: str                  # 声明类型:
                                     #   "pipeline_calculation" — 管线计算的数值
                                     #   "data_citation"        — 原始数据引用
                                     #   "trend_judgment"       — 趋势判断
                                     #   "business_assertion"   — 商业知识断言
                                     #   "qualitative_score"    — 分析 Agent 主观打分
    data_refs: list[str] = field(default_factory=list)
                                     # brief.md 中引用的数据段名称
    source_numbers: dict[str, float] = field(default_factory=dict)
                                     # 声明中引用的关键数字及来源
    confidence: str = "high"         # 分析 Agent 自评置信度: high/medium/low


# ══════════════════════════════════════════════════════════════
# Phase 5b — 逐条 CV 核查
# ══════════════════════════════════════════════════════════════


@dataclass
class VerifiedClaim:
    """CV Agent 对单条声明的核查结果。"""

    claim: AnalysisClaim | None = None  # 被核查的原始声明
    claim_id: str = ""                  # 声明 ID（冗余，方便模板使用）
    dimension: str = ""                 # 核查维度（冗余）
    claim_text: str = ""                # 原始声明文本（冗余）
    claim_type: str = ""                # 声明类型（冗余）

    judgment: str = ""                  # ✓源数据可支撑 / ⚠过度解读 / ✗与源数据矛盾 / ?缺乏证据
    evidence: str = ""                  # CV 引用的源数据证据
    suggestion: str = ""                # 修正建议
    severity: str = "INFO"             # INFO / WARNING / CRITICAL

    # 核查置信度
    cv_confidence: str = "medium"       # CV Agent 对自身判断的置信度: high/medium/low

    def to_dict(self) -> dict[str, Any]:
        """转为模板可用的字典。"""
        jc = "consistent"
        if self.judgment.startswith("✓"):
            jc = "consistent"
        elif self.judgment.startswith("⚠"):
            jc = "overstatement"
        elif self.judgment.startswith("✗"):
            jc = "conflict"
        elif self.judgment.startswith("?"):
            jc = "evidence_lack"
        return {
            "claim_id": self.claim_id or (self.claim.id if self.claim else ""),
            "dimension": self.dimension or (self.claim.dimension if self.claim else ""),
            "claim_text": self.claim_text or (self.claim.claim_text if self.claim else ""),
            "claim_type": self.claim_type or (self.claim.claim_type if self.claim else ""),
            "judgment": self.judgment,
            "judgment_class": jc,
            "evidence": self.evidence,
            "suggestion": self.suggestion,
            "severity": self.severity,
            "cv_confidence": self.cv_confidence,
        }


# ══════════════════════════════════════════════════════════════
# Phase 5b.5 — 分析 Agent 回炉修正
# ══════════════════════════════════════════════════════════════


@dataclass
class RevisedClaim:
    """分析 Agent 对 CV 核查结果做出的回应。"""

    claim: AnalysisClaim | None = None  # 原始声明
    claim_id: str = ""
    cv_judgment: str = ""              # CV 原始判断
    cv_evidence: str = ""              # CV 引用的源数据

    analyst_response: str = ""         # "accept" — 接受修正
                                       # "dispute" — 不同意
                                       # "clarify" — 澄清澄清

    revised_text: str | None = None    # 修正后的声明文本（若接受/澄清）
    rebuttal: str = ""                 # 坚持原声明的理由（若 dispute）

    def to_dict(self) -> dict[str, Any]:
        """转为模板可用的字典。"""
        return {
            "claim_id": self.claim_id,
            "dimension": self.claim.dimension if self.claim else "",
            "claim_text": self.claim.claim_text if self.claim else "",
            "cv_judgment": self.cv_judgment,
            "cv_evidence": self.cv_evidence,
            "analyst_response": self.analyst_response,
            "revised_text": self.revised_text or "",
            "rebuttal": self.rebuttal,
        }


# ══════════════════════════════════════════════════════════════
# 汇总结果
# ══════════════════════════════════════════════════════════════


@dataclass
class ClaimVerificationResult:
    """逐条核查 + 回炉修正的完整结果。"""

    ts_code: str = ""
    name: str = ""

    # Phase 5b: 逐条核查
    verified_claims: list[VerifiedClaim] = field(default_factory=list)

    # Phase 5b.5: 回炉修正
    revised_claims: list[RevisedClaim] = field(default_factory=list)
    revised_report: str = ""            # 修正后的分析报告全文

    # 统计
    total_claims: int = 0
    supported_count: int = 0            # ✓
    overstatement_count: int = 0       # ⚠
    conflict_count: int = 0            # ✗
    evidence_lack_count: int = 0       # ?

    # 修正统计
    accepted_count: int = 0
    disputed_count: int = 0
    clarified_count: int = 0

    # 总体评语
    overall_verdict: str = ""

    success: bool = False
    error: str = ""

    def refresh_stats(self) -> None:
        """从 verified_claims 重新计算统计量。"""
        self.total_claims = len(self.verified_claims)
        self.supported_count = sum(1 for v in self.verified_claims if v.judgment.startswith("✓"))
        self.overstatement_count = sum(1 for v in self.verified_claims if v.judgment.startswith("⚠"))
        self.conflict_count = sum(1 for v in self.verified_claims if v.judgment.startswith("✗"))
        self.evidence_lack_count = sum(1 for v in self.verified_claims if v.judgment.startswith("?"))

        self.accepted_count = sum(1 for r in self.revised_claims if r.analyst_response == "accept")
        self.disputed_count = sum(1 for r in self.revised_claims if r.analyst_response == "dispute")
        self.clarified_count = sum(1 for r in self.revised_claims if r.analyst_response == "clarify")

    def to_cv_issues(self) -> list[dict]:
        """提取 ⚠/✗/? 问题项，供 Phase 5c 根因反思使用。"""
        issues: list[dict] = []
        for v in self.verified_claims:
            if v.judgment.startswith("✓"):
                continue
            issues.append({
                "dimension": v.dimension or (v.claim.dimension if v.claim else ""),
                "judgment": v.judgment,
                "web_evidence": v.evidence,
                "evidence": v.evidence,
                "suggestion": v.suggestion,
            })
        return issues

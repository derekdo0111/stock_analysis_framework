"""
SharedContext — 三层不可变上下文，用于 LLM Agent 间数据传递。

三层架构:
1. Immutable Layer: 原始数据（Tushare 返回、计算中间产物）— 只读
2. Enriched Layer: 加工数据（行业对比、分位数、趋势）— 追加不可修改
3. Opinion Layer: Agent 产出（分析结果、验证结果）— 写入后不可修改
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from src.calculator.turtle_strategy.scoring import FinalScore


@dataclass
class SharedContext:
    """Agent 间共享的三层上下文。

    Usage:
        ctx = SharedContext(score)
        # Immutable: read only
        print(ctx.immutable["final_score"])
        # Enriched: append only
        ctx.add_enriched("industry_percentile", 0.85)
        # Opinion: write once
        ctx.set_opinion("analysis", analysis_result)
    """

    ts_code: str
    created_at: datetime = field(default_factory=datetime.now)

    # ── Layer 1: Immutable (只读原始数据) ──
    _immutable: dict[str, Any] = field(default_factory=dict)

    # ── Layer 2: Enriched (追加工数据) ──
    _enriched: dict[str, Any] = field(default_factory=dict)

    # ── Layer 3: Opinion (Agent 产出) ──
    _opinions: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        pass

    @classmethod
    def from_score(cls, score: FinalScore) -> SharedContext:
        """从 FinalScore 构造上下文。"""
        ctx = cls(ts_code=score.ts_code)
        ctx._immutable.update({
            "ts_code": score.ts_code,
            "name": score.name,
            "l2_score": score.l2_score,
            "l3_multiplier": score.l3_multiplier,
            "l4_score": score.l4_score,
            "l5_score": score.l5_score,
            "raw_total": score.raw_total,
            "final_score": score.final_score,
            "pool": score.pool,
            "pr_pct": score.pr_pct,
            "oe_quality": score.oe_quality,
        })
        return ctx

    # ── Immutable Layer ───────────────────────────────────

    @property
    def immutable(self) -> dict[str, Any]:
        """只读原始数据（返回拷贝）。"""
        return dict(self._immutable)

    def set_immutable(self, key: str, value: Any) -> None:
        """设置不可变数据（仅首次有效）。"""
        if key not in self._immutable:
            self._immutable[key] = value

    # ── Enriched Layer ────────────────────────────────────

    @property
    def enriched(self) -> dict[str, Any]:
        """加工数据（返回拷贝）。"""
        return dict(self._enriched)

    def add_enriched(self, key: str, value: Any) -> None:
        """追加加工数据。"""
        self._enriched[key] = value

    # ── Opinion Layer ─────────────────────────────────────

    @property
    def opinions(self) -> dict[str, Any]:
        """Agent 产出（返回拷贝）。"""
        return dict(self._opinions)

    def set_opinion(self, agent_name: str, result: Any) -> bool:
        """写入 Agent 产出（仅首次写入有效，防止覆盖）。

        Returns:
            True if write succeeded, False if already written
        """
        if agent_name in self._opinions:
            return False
        self._opinions[agent_name] = result
        return True

    def get_opinion(self, agent_name: str) -> Any | None:
        """获取 Agent 产出。"""
        return self._opinions.get(agent_name)

    # ── Summary ───────────────────────────────────────────

    def summary(self) -> str:
        """上下文摘要。"""
        return (
            f"SharedContext({self.ts_code}): "
            f"immutable={len(self._immutable)} keys, "
            f"enriched={len(self._enriched)} keys, "
            f"opinions={list(self._opinions.keys())}"
        )


__all__ = ["SharedContext"]

"""
股票池管理 — 核心池 / 观察池 / 备选池。

根据 FinalScore.final_score 自动分类:
- core (核心池): final_score >= 75
- observe (观察池): 55 <= final_score < 75
- reserve (备选池): final_score < 55
- rejected (否决): HardGate 否决或分类排除
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.turtle.calculator.scoring import FinalScore

from src.turtle.screening.hard_gate import HardGateResult
from src.turtle.screening.classifier import ClassifyResult


@dataclass
class PoolEntry:
    """股票池条目。"""
    ts_code: str
    name: str = ""
    final_score: float = 0.0
    pool: str = "reserve"
    l2_score: float = 0.0
    l3_multiplier: float = 1.0
    l4_score: float = 0.0
    l5_score: float = 0.0
    pr_pct: float = 0.0
    classify_type: str = ""
    hard_gate_passed: bool = True
    hard_gate_details: Optional[HardGateResult] = None
    classify_details: Optional[ClassifyResult] = None


@dataclass
class StockPool:
    """三池管理：核心/观察/备选 + 否决名单。

    Usage:
        pool = StockPool()
        pool.add(scoring_result)
        print(pool.core_pool)  # ['600519.SH', ...]
        print(pool.summary())  # 统计摘要
    """

    core: list[PoolEntry] = field(default_factory=list)       # >= 75
    observe: list[PoolEntry] = field(default_factory=list)     # 55 ~ 74
    reserve: list[PoolEntry] = field(default_factory=list)     # < 55
    rejected: list[PoolEntry] = field(default_factory=list)    # HardGate / 分类否决

    # ── Thresholds from turtle_constants.yaml ──
    CORE_THRESHOLD: float = 75.0
    OBSERVE_THRESHOLD: float = 55.0

    # ── Pool methods ───────────────────────────────────────

    def add(self, score: FinalScore, hard_gate: HardGateResult | None = None,
            classify: ClassifyResult | None = None) -> PoolEntry:
        """添加一只股票的评分结果到对应池。"""
        entry = PoolEntry(
            ts_code=score.ts_code,
            name=score.name,
            final_score=score.final_score,
            pool=self._classify_pool(score, hard_gate, classify),
            l2_score=score.l2_score,
            l3_multiplier=score.l3_multiplier,
            l4_score=score.l4_score,
            l5_score=score.l5_score,
            pr_pct=score.pr_pct,
            classify_type=classify.classify_type if classify else "",
            hard_gate_passed=hard_gate.passed if hard_gate else True,
            hard_gate_details=hard_gate,
            classify_details=classify,
        )

        if not entry.hard_gate_passed or self._is_classify_rejected(classify):
            self.rejected.append(entry)
        elif entry.final_score >= self.CORE_THRESHOLD:
            self.core.append(entry)
        elif entry.final_score >= self.OBSERVE_THRESHOLD:
            self.observe.append(entry)
        else:
            self.reserve.append(entry)

        return entry

    def get_pool(self, pool_name: str) -> list[PoolEntry]:
        """获取指定池中的所有股票。"""
        pools = {
            "core": self.core,
            "observe": self.observe,
            "reserve": self.reserve,
            "rejected": self.rejected,
        }
        return pools.get(pool_name, [])

    def get_stock(self, ts_code: str) -> PoolEntry | None:
        """查找某只股票在哪个池。"""
        for pool_list in [self.core, self.observe, self.reserve, self.rejected]:
            for entry in pool_list:
                if entry.ts_code == ts_code:
                    return entry
        return None

    def all_passed(self) -> list[PoolEntry]:
        """所有通过 HardGate + 未被分类排除的股票（三池合并）。"""
        return self.core + self.observe + self.reserve

    def top_n(self, n: int = 5) -> list[PoolEntry]:
        """按 FinalScore 降序返回 Top N。"""
        all_stocks = self.all_passed()
        return sorted(all_stocks, key=lambda x: x.final_score, reverse=True)[:n]

    def summary(self) -> str:
        """打印池统计。"""
        lines = [
            f"=== 股票池统计 ===",
            f"核心池 (>= {self.CORE_THRESHOLD}): {len(self.core)} 只",
            f"观察池 ({self.OBSERVE_THRESHOLD}~{self.CORE_THRESHOLD}): {len(self.observe)} 只",
            f"备选池 (< {self.OBSERVE_THRESHOLD}): {len(self.reserve)} 只",
            f"否决: {len(self.rejected)} 只",
            f"---",
        ]
        for entry in self.top_n(5):
            lines.append(
                f"  {entry.ts_code} {entry.name}: {entry.final_score:.1f} [{entry.pool}]"
            )
        return "\n".join(lines)

    # ── Internal helpers ───────────────────────────────────

    @staticmethod
    def _classify_pool(score: FinalScore, hard_gate: HardGateResult | None,
                       classify: ClassifyResult | None) -> str:
        if hard_gate and not hard_gate.passed:
            return "rejected"
        if StockPool._is_classify_rejected(classify):
            return "rejected"
        if score.final_score >= StockPool.CORE_THRESHOLD:
            return "core"
        if score.final_score >= StockPool.OBSERVE_THRESHOLD:
            return "observe"
        return "reserve"

    @staticmethod
    def _is_classify_rejected(classify: ClassifyResult | None) -> bool:
        if classify is None:
            return False
        excluded = {"CYCLICAL", "FINANCIAL", "GROWTH_NO_DIVIDEND"}
        return classify.classify_type in excluded

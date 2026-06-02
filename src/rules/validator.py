"""规则校验器 — 校验 YAML 规则文件的结构和约束。"""

from __future__ import annotations

from typing import Any

from loguru import logger
from pydantic import ValidationError

from src.rules.schemas import RuleSet


class RuleValidator:
    """规则文件离线校验器。

    在加载 YAML → Pydantic 之后，执行额外的跨文件一致性检查。
    """

    def __init__(self, rules: RuleSet):
        self._rules = rules
        self._warnings: list[str] = []
        self._errors: list[str] = []

    def validate_all(self) -> tuple[bool, list[str], list[str]]:
        """执行所有校验。

        Returns:
            (is_valid, warnings, errors)
        """
        self._warnings = []
        self._errors = []

        # HardGate thresholds
        self._check_hard_gate()

        # L2 thresholds
        self._check_l2()

        # Turtle constants
        self._check_turtle()

        # Print summary
        for w in self._warnings:
            logger.warning(w)
        for e in self._errors:
            logger.error(e)

        return len(self._errors) == 0, self._warnings, self._errors

    # ── Individual checks ──────────────────────────────────

    def _check_hard_gate(self) -> None:
        hg = getattr(self._rules, 'hard_gate', None)
        if hg is None:
            self._errors.append("hard_gate_rules 未加载")
            return
        # 暴涨暴跌阈值合理性
        surge = getattr(hg, 'surge_check', None)
        if surge:
            upper = getattr(surge, 'upper_threshold', None)
            lower = getattr(surge, 'lower_threshold', None)
            if upper and lower and upper <= abs(lower):
                self._warnings.append(
                    f"暴涨阈值({upper}) <= 暴跌阈值绝对值({abs(lower)}), 可能不合理"
                )

    def _check_l2(self) -> None:
        l2 = getattr(self._rules, 'l2_screener', None)
        if l2 is None:
            self._errors.append("l2_screener_rules 未加载")
            return
        max_score = getattr(l2, 'max_score', 20)
        if max_score != 20:
            self._warnings.append(f"L2 max_score = {max_score} (预期 20)")

    def _check_turtle(self) -> None:
        tc = getattr(self._rules, 'turtle_constants', None)
        if tc is None:
            self._errors.append("turtle_constants 未加载")
            return
        # PR 阈值降序校验应该已在 Pydantic validator 中处理
        # 这里做补充检查
        pass


__all__ = ["RuleValidator"]

"""数据校验模块 — 通用校验工具函数。"""

from __future__ import annotations

from typing import Any


def validate_ts_code(ts_code: str) -> bool:
    """校验 Tushare 股票代码格式。

    Args:
        ts_code: 如 "600519.SH", "000858.SZ"

    Returns:
        True if valid format
    """
    if not ts_code or "." not in ts_code:
        return False
    code, market = ts_code.split(".", 1)
    if not code.isdigit() or len(code) != 6:
        return False
    return market in ("SH", "SZ", "BJ")


def validate_year(year: int) -> bool:
    """校验年份合理性（1990 ~ 当前+1）。"""
    import datetime
    current = datetime.date.today().year
    return 1990 <= year <= current + 1


def ensure_positive(value: float, default: float = 0.0) -> float:
    """确保数值非负。"""
    return max(value, 0.0) if value is not None else default


def ensure_non_zero(value: float, default: float = 1.0) -> float:
    """确保数值非零。"""
    if value is None or value == 0:
        return default
    return value


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """安全除法（分母为0返回默认值）。"""
    if denominator is None or denominator == 0:
        return default
    return numerator / denominator


def clip_score(score: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """夹取分数到合法范围。"""
    return max(min_val, min(score, max_val))


__all__ = [
    "validate_ts_code",
    "validate_year",
    "ensure_positive",
    "ensure_non_zero",
    "safe_divide",
    "clip_score",
]

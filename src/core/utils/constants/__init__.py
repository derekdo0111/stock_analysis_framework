"""常量定义 — 框架级别常量。"""

from __future__ import annotations

# ── 版本 ──
VERSION: str = "0.21.0-dev"

# ── 股票市场 ──
SUPPORTED_MARKETS: list[str] = ["SH", "SZ", "BJ"]

# ── 策略名称 ──
STRATEGY_TURTLE: str = "turtle_strategy"

# ── 池分类阈值 (默认值，实际从 YAML 加载) ──
POOL_CORE_MIN: float = 75.0
POOL_OBSERVE_MIN: float = 55.0

# ── 时间窗口 ──
DEFAULT_LOOKBACK_YEARS: int = 5
MIN_LISTING_YEARS: int = 5

# ── 文件格式 ──
SUPPORTED_STORAGE_FORMATS: list[str] = ["json", "parquet", "both"]

# ── Tushare 积分阈值 ──
TUSHARE_LEVEL1_POINTS: int = 120     # 基础接口
TUSHARE_LEVEL2_POINTS: int = 2000    # 全量接口

__all__ = [
    "VERSION",
    "SUPPORTED_MARKETS",
    "STRATEGY_TURTLE",
    "POOL_CORE_MIN",
    "POOL_OBSERVE_MIN",
    "DEFAULT_LOOKBACK_YEARS",
    "MIN_LISTING_YEARS",
    "SUPPORTED_STORAGE_FORMATS",
    "TUSHARE_LEVEL1_POINTS",
    "TUSHARE_LEVEL2_POINTS",
]

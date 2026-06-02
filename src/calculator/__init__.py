"""计算引擎层 — 龟龟策略 / 财务比率"""

from src.calculator.turtle_strategy import (
    OECalculator,
    OECalculationResult,
    PRCalculator,
    PRCalculationResult,
    L5Calculator,
    L5Result,
    TurtleScorer,
    FinalScore,
    quick_score,
    CashRecon,
    CashReconResult,
    SOTPAdjuster,
    SOTPResult,
    get_constants,
)
from src.calculator.registry import StrategyRegistry, get_registry, StrategyModule
from src.calculator.financial_ratios import (
    DuPontResult,
    CAGRResult,
    dupont_analysis,
    calculate_cagr,
    calculate_percentile,
    calculate_percentiles,
)

__all__ = [
    "OECalculator",
    "OECalculationResult",
    "PRCalculator",
    "PRCalculationResult",
    "L5Calculator",
    "L5Result",
    "TurtleScorer",
    "FinalScore",
    "quick_score",
    "CashRecon",
    "CashReconResult",
    "SOTPAdjuster",
    "SOTPResult",
    "get_constants",
    "StrategyRegistry",
    "get_registry",
    "StrategyModule",
    "DuPontResult",
    "CAGRResult",
    "dupont_analysis",
    "calculate_cagr",
    "calculate_percentile",
    "calculate_percentiles",
]

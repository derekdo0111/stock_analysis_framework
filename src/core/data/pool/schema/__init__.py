"""数据模型 — 19 Pydantic v2 Schema (双轨设计)"""

from src.core.data.pool.schema.models import (
    # Part A: 10 Tushare 接口模型
    BalanceSheet,
    AuditOpinion,
    CashFlowStatement,
    DailyBasic,
    DailyPrice,
    DividendRecord,
    FinancialIndicator,
    IncomeStatement,
    StockBasic,
    TradeCalendar,
    # Part B: 9 分析中间产物模型
    ExtrapolationScore,
    FinalAnalysisScore,
    OEQualityLabel,
    OEPathAResult,
    OEPathBResult,
    PenetrationReturnResult,
    PositionRecommendation,
    StockProfile,
    ValueTrapResult,
)

__all__ = [
    # Tushare
    "BalanceSheet",
    "AuditOpinion",
    "CashFlowStatement",
    "DailyBasic",
    "DailyPrice",
    "DividendRecord",
    "FinancialIndicator",
    "IncomeStatement",
    "StockBasic",
    "TradeCalendar",
    # Analytics
    "ExtrapolationScore",
    "FinalAnalysisScore",
    "OEQualityLabel",
    "OEPathAResult",
    "OEPathBResult",
    "PenetrationReturnResult",
    "PositionRecommendation",
    "StockProfile",
    "ValueTrapResult",
]

"""数据池 — 数据模型/校验/存储/转换 v0.19"""

from src.data_pool.bundle import StockDataBundle
from src.data_pool.schema.models import (
    BalanceSheet,
    AuditOpinion,
    CashFlowStatement,
    DailyBasic,
    DailyPrice,
    DividendRecord,
    ExtrapolationScore,
    FinalAnalysisScore,
    FinancialIndicator,
    IncomeStatement,
    OEQualityLabel,
    OEPathBResult,
    PenetrationReturnResult,
    PositionRecommendation,
    StockBasic,
    StockProfile,
    TradeCalendar,
    ValueTrapResult,
)
from src.data_pool.schema.disposable_cash import DisposableCashResult, DisposableCashCalculator
from src.data_pool.storage.local_storage import LocalStorage
from src.data_pool.validator.data_validator import DataValidator

__all__ = [
    # Bundle
    "StockDataBundle",
    # Schemas
    "AuditOpinion",
    "BalanceSheet",
    "CashFlowStatement",
    "DailyBasic",
    "DailyPrice",
    "DividendRecord",
    "ExtrapolationScore",
    "FinalAnalysisScore",
    "FinancialIndicator",
    "IncomeStatement",
    "OEQualityLabel",
    "OEPathBResult",
    "PenetrationReturnResult",
    "PositionRecommendation",
    "StockBasic",
    "StockProfile",
    "TradeCalendar",
    "ValueTrapResult",
    # v0.19
    "DisposableCashResult",
    "DisposableCashCalculator",
    # Storage
    "LocalStorage",
    # Validator
    "DataValidator",
]

"""
Unit tests for data pool: schemas, storage, validator.

Covers:
- 19 Pydantic schema validation (all models constructable)
- LocalStorage JSON/Parquet roundtrip
- DataValidator batch validation with error collection
- StockProfile fixture integrity
"""

import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from src.data_pool.schema.models import (
    AuditOpinion,
    BalanceSheet,
    CashFlowStatement,
    DailyBasic,
    DailyPrice,
    DividendRecord,
    ExtrapolationScore,
    FinalAnalysisScore,
    FinancialIndicator,
    IncomeStatement,
    OEQualityLabel,
    OEPathAResult,
    OEPathBResult,
    PenetrationReturnResult,
    PositionRecommendation,
    StockBasic,
    StockProfile,
    TradeCalendar,
    ValueTrapResult,
)
from src.data_pool.storage.local_storage import LocalStorage
from src.data_pool.validator.data_validator import DataValidator


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

MOCK_TS_CODE = "600519.SH"
MOCK_DATE = date(2025, 5, 30)


# ═══════════════════════════════════════════════════════════════
# Test: 10 Tushare interface models
# ═══════════════════════════════════════════════════════════════

class TestTushareModels:
    """All 10 Tushare interface models construct with minimal data."""

    def test_stock_basic(self):
        m = StockBasic(ts_code=MOCK_TS_CODE, name="贵州茅台", industry="白酒")
        assert m.industry == "白酒"
        assert m.list_status == "L"
        assert m.raw_tushare_data == {}

    def test_audit_opinion(self):
        m = AuditOpinion(ts_code=MOCK_TS_CODE, audit_result="标准无保留意见")
        assert m.audit_result == "标准无保留意见"

    def test_daily_basic(self):
        m = DailyBasic(ts_code=MOCK_TS_CODE, trade_date=MOCK_DATE, pe=25.5)
        assert m.pe == 25.5

    def test_financial_indicator(self):
        m = FinancialIndicator(ts_code=MOCK_TS_CODE, roe=38.4, grossprofit_margin=91.9)
        assert m.roe == 38.4

    def test_income_statement(self):
        m = IncomeStatement(
            ts_code=MOCK_TS_CODE, total_revenue=1.74e11, n_income=8.93e10
        )
        assert m.total_revenue == 1.74e11

    def test_cashflow_statement(self):
        m = CashFlowStatement(ts_code=MOCK_TS_CODE, n_cashflow_act=9.24e10)
        assert m.n_cashflow_act == 9.24e10

    def test_balance_sheet(self):
        m = BalanceSheet(ts_code=MOCK_TS_CODE, money_cap=5.0e10, fix_assets=3.0e10)
        assert m.money_cap == 5.0e10

    def test_dividend_record(self):
        m = DividendRecord(ts_code=MOCK_TS_CODE, cash_div=25.91)
        assert m.cash_div == 25.91

    def test_daily_price(self):
        m = DailyPrice(ts_code=MOCK_TS_CODE, trade_date=MOCK_DATE, close=1522.0)
        assert m.close == 1522.0
        assert m.pct_chg is None

    def test_trade_calendar(self):
        m = TradeCalendar(exchange="SSE", cal_date=MOCK_DATE, is_open=1)
        assert m.is_open == 1

    def test_raw_tushare_preserved(self):
        """Raw Tushare data survives in the model."""
        raw = {"ts_code": MOCK_TS_CODE, "extra_field": 999}
        m = StockBasic(ts_code=MOCK_TS_CODE, name="test", raw_tushare_data=raw)
        assert m.raw_tushare_data["extra_field"] == 999


# ═══════════════════════════════════════════════════════════════
# Test: 9 Analytics models
# ═══════════════════════════════════════════════════════════════

class TestAnalyticsModels:
    """All 9 analytics models construct correctly."""

    def test_stock_profile(self):
        p = StockProfile(
            ts_code=MOCK_TS_CODE,
            name="茅台",
            industry="白酒",
            roe_5y_median=30.0,
            market_cap=22000,
            company_class="STANDARD_CONSUMER",
        )
        assert p.company_class == "STANDARD_CONSUMER"
        assert p.oe_cf_history == []

    def test_oe_path_b(self):
        m = OEPathBResult(
            ts_code=MOCK_TS_CODE,
            maintenance_coefficient=0.45,
            oe_cf_values=[9e10, 8.5e10, 9.2e10, 8.8e10, 9.5e10],
            oe_cf_median=9.0e10,
        )
        assert m.oe_cf_median == 9.0e10

    def test_oe_path_a(self):
        m = OEPathAResult(
            ts_code=MOCK_TS_CODE, oe_income_values=[8e10, 8.5e10, 9e10, 9.5e10, 10e10]
        )
        assert len(m.oe_income_values) == 5

    def test_oe_quality_label_trusted(self):
        m = OEQualityLabel(
            ts_code=MOCK_TS_CODE,
            label="🟢 可信",
            oe_cf_to_profit_ratio=0.85,
            oe_cf_cv=0.2,
        )
        assert "可信" in m.label

    def test_penetration_return(self):
        m = PenetrationReturnResult(
            ts_code=MOCK_TS_CODE,
            oe_cf_median=9.0e10,
            market_cap=22000,
            pr_raw=0.041,
            pr_pct=4.1,
            l4_starting_score=0,
            l4_score=0,
        )
        assert m.pr_pct == 4.1

    def test_extrapolation_score(self):
        m = ExtrapolationScore(
            ts_code=MOCK_TS_CODE,
            dimensions={"revenue_stability": 5, "margin_stability": 4},
            total=27,
            level="高可行",
        )
        assert m.level == "高可行"

    def test_value_trap_result(self):
        m = ValueTrapResult(
            ts_code=MOCK_TS_CODE,
            traps_triggered=[],
            total_score=0,
            level="低风险",
        )
        assert m.level == "低风险"

    def test_position_recommendation(self):
        m = PositionRecommendation(
            ts_code=MOCK_TS_CODE,
            extrapolation_level="high",
            trap_level="low",
            max_position_pct=15,
            label="10~15%",
            l5_score=25,
        )
        assert m.max_position_pct == 15

    def test_final_analysis_score(self):
        m = FinalAnalysisScore(
            ts_code=MOCK_TS_CODE,
            name="茅台",
            l2_score=18,
            l3_multiplier=1.2,
            l4_score=35,
            l5_score=22,
            raw_total=75,
            final_score=90,
            pool="核心池",
            business_model="优",
        )
        assert m.pool == "核心池"
        assert m.final_score == 90

    def test_final_score_auto_correct_raw(self):
        """When raw_total drift from L2+L4+L5, auto-correct."""
        m = FinalAnalysisScore(
            ts_code=MOCK_TS_CODE,
            name="test",
            l2_score=15,
            l3_multiplier=1.0,
            l4_score=30,
            l5_score=20,
            raw_total=66.0,  # 15+30+20=65, small drift OK
            final_score=66.0,
            pool="观察池",
        )
        # raw_total should have been corrected to 65
        assert abs(m.raw_total - 65.0) < 0.2


# ═══════════════════════════════════════════════════════════════
# Test: Storage (JSON + Parquet)
# ═══════════════════════════════════════════════════════════════

class TestLocalStorage:
    @pytest.fixture
    def store(self, tmp_path: Path):
        return LocalStorage(tmp_path / "data")

    def test_save_load_json(self, store: LocalStorage):
        df = pd.DataFrame({"ts_code": ["A", "B"], "value": [1.0, 2.0]})
        store.save(df, "test_json", format="json")
        loaded = store.load("test_json", prefer="json")
        assert len(loaded) == 2
        assert list(loaded["ts_code"]) == ["A", "B"]

    def test_save_load_parquet(self, store: LocalStorage):
        df = pd.DataFrame({"ts_code": ["A", "B"], "value": [1.0, 2.0]})
        store.save(df, "test_pq", format="parquet")
        loaded = store.load("test_pq", prefer="parquet")
        assert len(loaded) == 2

    def test_save_both_formats(self, store: LocalStorage):
        df = pd.DataFrame({"x": [1]})
        saved = store.save(df, "both_test", format="both")
        assert "json" in saved
        assert "parquet" in saved
        assert store.exists("both_test")

    def test_load_nonexistent_raises(self, store: LocalStorage):
        with pytest.raises(FileNotFoundError):
            store.load("nonexistent")

    def test_list_datasets(self, store: LocalStorage):
        store.save(pd.DataFrame({"a": [1]}), "ds1", format="json")
        store.save(pd.DataFrame({"b": [2]}), "ds2", format="parquet")
        names = store.list_datasets()
        assert "ds1" in names
        assert "ds2" in names

    def test_delete(self, store: LocalStorage):
        store.save(pd.DataFrame({"a": [1]}), "to_delete", format="both")
        store.delete("to_delete")
        assert not store.exists("to_delete")

    def test_roundtrip_floats(self, store: LocalStorage):
        """Floats survive JSON and Parquet roundtrip."""
        df = pd.DataFrame({"roe": [38.4283, 25.1], "gross_margin": [91.9312, 65.0]})
        store.save(df, "floats", format="both")
        loaded = store.load("floats")
        assert loaded["roe"].iloc[0] == pytest.approx(38.4283, rel=1e-4)


# ═══════════════════════════════════════════════════════════════
# Test: Validator
# ═══════════════════════════════════════════════════════════════

class TestDataValidator:
    def test_validate_batch_all_valid(self):
        v = DataValidator()
        df = pd.DataFrame({
            "exchange": ["SSE", "SZSE"],
            "cal_date": [date(2025, 5, 30), date(2025, 5, 29)],
            "is_open": [1, 1],
        })
        models, errors = v.validate_batch(TradeCalendar, df)
        assert len(models) == 2
        assert len(errors) == 0
        assert models[0].is_open == 1

    def test_validate_batch_mixed(self):
        v = DataValidator()
        df = pd.DataFrame({
            "exchange": ["SSE", "SSE"],
            "cal_date": [date(2025, 5, 30), date(2025, 5, 29)],
            "is_open": [1, "invalid"],  # Second row type mismatch
        })
        models, errors = v.validate_batch(TradeCalendar, df)
        assert len(models) == 1
        assert len(errors) == 1
        assert errors[0]["ts_code"] == "N/A"

    def test_validate_single_strict(self):
        v = DataValidator(strict=True)
        record = {"exchange": "SSE", "cal_date": date(2025, 5, 30), "is_open": 1}
        m = v.validate_single(TradeCalendar, record)
        assert m.is_open == 1

    def test_validate_single_invalid(self):
        v = DataValidator(strict=True)
        with pytest.raises(ValidationError):
            v.validate_single(TradeCalendar, {"exchange": "SSE"})


# ═══════════════════════════════════════════════════════════════
# Test: StockProfile fixture integrity
# ═══════════════════════════════════════════════════════════════

class TestStockProfileFixtures:
    """StockProfile covers all code paths needed by tests."""

    def test_perfect_profile(self):
        p = StockProfile(
            ts_code="600519.SH",
            name="贵州茅台",
            industry="白酒",
            list_years=23,
            is_hsgt=True,
            audit_opinion="标准无保留意见",
            roe_5y_median=32.0,
            gross_margin_5y_median=92.0,
            debt_ratio=25.0,
            op_cf_to_np_5y_median=95.0,
            pe=20.0,
            pb=5.0,
            ps=3.0,
            dividend_yield=2.5,
            avg_turnover=5.0,
            oe_cf_history=[8.5e10, 8.8e10, 9.0e10, 9.2e10, 9.5e10],
            oe_cf_median_5y=9.0e10,
            oe_cf_cv=0.05,
            oe_cf_cagr_3y=0.03,
            market_cap=22000,
            company_class="STANDARD_CONSUMER",
            expected_l2_score=18.5,
            expected_pr=0.0409,
            expected_final_score=90.0,
        )
        assert p.company_class == "STANDARD_CONSUMER"
        assert p.expected_l2_score == 18.5

    def test_excluded_types(self):
        """CYCLICAL, FINANCIAL, GROWTH_NO_DIVIDEND profiles work."""
        for cls in ["CYCLICAL", "FINANCIAL", "GROWTH_NO_DIVIDEND"]:
            p = StockProfile(ts_code="000001.SZ", name="test", industry="test", company_class=cls)
            assert p.company_class == cls

    def test_st_stock(self):
        p = StockProfile(ts_code="000004.SZ", name="*ST国华", industry="软件", is_st=True)
        assert p.is_st is True

    def test_holding_company(self):
        p = StockProfile(
            ts_code="600050.SH",
            name="控股型",
            industry="综合",
            total_assets=10000,
            tradable_fin_assets=3000,  # 交易性金融资产
            long_term_equity_invest=2000,  # 长期股权投资
            company_class="HOLDING_COMPANY",
        )
        # (Tradable + LTEquity) / Total = 50% > 40% → HOLDING
        assert p.company_class == "HOLDING_COMPANY"

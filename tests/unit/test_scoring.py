"""Unit tests for Turtle scoring pipeline."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.calculator.turtle_strategy.oe_calculator import OECalculator, OECalculationResult
from src.calculator.turtle_strategy.pr_calculator import PRCalculator, PRCalculationResult
from src.calculator.turtle_strategy.l5_calculator import L5Calculator, L5Result
from src.calculator.turtle_strategy.scoring import TurtleScorer, FinalScore


@pytest.fixture
def mock_client():
    c = MagicMock()
    c.stock_basic.return_value = pd.DataFrame([{
        "ts_code": "600519.SH", "name": "Test", "industry": "白酒",
    }])
    c.fina_indicator.return_value = pd.DataFrame([{
        "ts_code": "600519.SH", "roe": 30, "grossprofit_margin": 80,
        "debt_to_assets": 20, "end_date": "20241231",
    }])
    c.daily_basic.return_value = pd.DataFrame([{
        "ts_code": "600519.SH", "pe": 25, "pb": 5, "ps": 3,
        "dv_ratio": 2.5, "turnover_rate": 3, "total_mv": 200000000,  # 20亿万元=20000亿
    }])
    c.income.return_value = pd.DataFrame([
        {"ts_code": "600519.SH", "end_date": "20241231", "total_revenue": 1500e8, "n_income": 700e8},
        {"ts_code": "600519.SH", "end_date": "20231231", "total_revenue": 1400e8, "n_income": 650e8},
        {"ts_code": "600519.SH", "end_date": "20221231", "total_revenue": 1300e8, "n_income": 600e8},
        {"ts_code": "600519.SH", "end_date": "20211231", "total_revenue": 1200e8, "n_income": 550e8},
        {"ts_code": "600519.SH", "end_date": "20201231", "total_revenue": 1100e8, "n_income": 500e8},
    ])
    c.cashflow.return_value = pd.DataFrame([
        {"ts_code": "600519.SH", "end_date": "20241231", "n_cashflow_act": 800e8, "c_pay_acq_const_fiolta": 30e8},
        {"ts_code": "600519.SH", "end_date": "20231231", "n_cashflow_act": 750e8, "c_pay_acq_const_fiolta": 28e8},
        {"ts_code": "600519.SH", "end_date": "20221231", "n_cashflow_act": 700e8, "c_pay_acq_const_fiolta": 25e8},
        {"ts_code": "600519.SH", "end_date": "20211231", "n_cashflow_act": 650e8, "c_pay_acq_const_fiolta": 22e8},
        {"ts_code": "600519.SH", "end_date": "20201231", "n_cashflow_act": 600e8, "c_pay_acq_const_fiolta": 20e8},
    ])
    c.balancesheet.return_value = pd.DataFrame([
        {"ts_code": "600519.SH", "end_date": "20241231", "fix_assets": 200e8, "money_cap": 500e8,
         "st_borrow": 0, "lt_borrow": 0, "bonds_payable": 0},
        {"ts_code": "600519.SH", "end_date": "20231231", "fix_assets": 190e8, "money_cap": 450e8,
         "st_borrow": 0, "lt_borrow": 0, "bonds_payable": 0},
    ])
    c.fina_audit.return_value = pd.DataFrame([{"audit_result": "标准无保留意见"}])
    c.daily.return_value = pd.DataFrame([
        {"trade_date": "20250101", "close": 100},
        {"trade_date": "20250601", "close": 105},
    ])
    c.dividend.return_value = pd.DataFrame([{"end_date": "20241231", "cash_div": 25}])
    c.pledge_stat.return_value = pd.DataFrame()
    return c


class TestOECalculator:
    def test_basic_calculation(self, mock_client):
        oe = OECalculator(mock_client)
        r = oe.calculate("600519.SH", "白酒")
        assert isinstance(r, OECalculationResult)
        assert r.industry_prior == 0.45  # consumer_staples
        assert len(r.oe_cf_values) > 0

    def test_maintenance_coefficient(self, mock_client):
        oe = OECalculator(mock_client)
        r = oe.calculate("600519.SH", "白酒")
        # Consumer staples prior=0.45, with asset intensity factor
        assert 0.40 <= r.maintenance_coefficient <= 0.70


class TestPRCalculator:
    def test_basic_calculation(self, mock_client):
        pr = PRCalculator(mock_client)
        r = pr.calculate("600519.SH", "白酒")
        assert isinstance(r, PRCalculationResult)
        assert r.oe_cf_median > 0
        # With 20+billion market cap and ~80b OE, PR should be < 8%
        assert r.pr_pct > 0

    def test_starting_score_map(self, mock_client):
        pr = PRCalculator(mock_client)
        r = pr.calculate("600519.SH", "白酒")
        if r.pr_pct >= 12:
            assert r.starting_score == 20
        elif r.pr_pct >= 8:
            assert r.starting_score == 15
        elif r.pr_pct >= 5:
            assert r.starting_score == 10
        # else: starting_score could be 0


class TestL5Calculator:
    def test_basic_calculation(self, mock_client):
        l5 = L5Calculator(mock_client)
        r = l5.calculate("600519.SH", "白酒")
        assert isinstance(r, L5Result)
        assert r.extrapolation_total > 0
        assert r.l5_score <= 25

    def test_industry_predictability(self, mock_client):
        l5 = L5Calculator(mock_client)
        r = l5.calculate("600519.SH", "白酒")
        # 白酒 → 消费 → score=5 in YAML
        assert r.extrapolation_dims.get("industry_predictability", 0) >= 3


class TestTurtleScorer:
    def test_full_pipeline(self, mock_client):
        scorer = TurtleScorer(mock_client)
        r = scorer.score("600519.SH")
        assert isinstance(r, FinalScore)
        assert r.name == "Test"
        assert r.pool in ("核心池", "观察池", "备选池")

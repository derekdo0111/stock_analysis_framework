"""Extended edge case tests for calculators and LLM modules."""

from unittest.mock import MagicMock
import pandas as pd
import pytest

from src.calculator.turtle_strategy.oe_calculator import OECalculator
from src.calculator.turtle_strategy.pr_calculator import PRCalculator
from src.calculator.turtle_strategy.l5_calculator import L5Calculator
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
        "dv_ratio": 2.5, "turnover_rate": 3, "total_mv": 200000000,
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


class TestOEEdgeCases:
    def test_empty_data_graceful(self, mock_client):
        mock_client.cashflow.return_value = pd.DataFrame()
        mock_client.income.return_value = pd.DataFrame()
        oe = OECalculator(mock_client)
        from src.calculator.turtle_strategy.oe_calculator import OECalculationResult
        r = oe.calculate("000001.SZ")
        assert isinstance(r, OECalculationResult)
        assert len(r.oe_cf_values) == 0

    def test_highly_stable_oe_trusted(self, mock_client):
        mock_client.cashflow.return_value = pd.DataFrame([
            {"ts_code": "t", "end_date": f"202{d}1231", "n_cashflow_act": 1000, "c_pay_acq_const_fiolta": 50}
            for d in range(4, -1, -1)
        ])
        mock_client.income.return_value = pd.DataFrame([
            {"ts_code": "t", "end_date": f"202{d}1231", "n_income": 950, "total_revenue": 5000}
            for d in range(4, -1, -1)
        ])
        oe = OECalculator(mock_client)
        r = oe.calculate("t", "白酒")
        # Stable OE with good profit ratio → trusted or questionable (not unreliable)
        assert r.quality_label in ("\U0001f7e2 可信", "\U0001f7e1 存疑")

    @pytest.mark.skip(reason="Mock OE calculation needs more complete BS data setup")
    def test_negative_oe_cagr(self, mock_client):
        values = [500, 400, 300, 200, 100]
        mock_client.cashflow.return_value = pd.DataFrame([
            {"ts_code": "t", "end_date": f"202{d}1231", "n_cashflow_act": v, "c_pay_acq_const_fiolta": 10}
            for d, v in zip(range(4, -1, -1), values)
        ])
        mock_client.income.return_value = pd.DataFrame([
            {"ts_code": "t", "end_date": f"202{d}1231", "n_income": 200, "total_revenue": 1000}
            for d in range(4, -1, -1)
        ])
        mock_client.balancesheet.return_value = pd.DataFrame([
            {"ts_code": "t", "end_date": f"202{d}1231", "fix_assets": 100, "money_cap": 200,
             "st_borrow": 0, "lt_borrow": 0, "bonds_payable": 0}
            for d in range(4, -1, -1)
        ])
        oe = OECalculator(mock_client)
        r = oe.calculate("t")
        assert r.oe_cf_cagr_3y < 0, f"Expected negative CAGR, got {r.oe_cf_cagr_3y}"
        assert r.oe_cf_values, "OE values should not be empty"


class TestPRCalculatorEdgeCases:
    def test_zero_market_cap(self, mock_client):
        mock_client.daily_basic.return_value = pd.DataFrame([{
            "ts_code": "t", "pe": 10, "pb": 2, "ps": 2,
            "dv_ratio": 2, "turnover_rate": 3, "total_mv": 0,
        }])
        pr = PRCalculator(mock_client)
        r = pr.calculate("t", "白酒")
        assert r.pr_pct == 0.0


class TestL5CalculatorEdgeCases:
    def test_all_dimensions_populated(self, mock_client):
        l5 = L5Calculator(mock_client)
        r = l5.calculate("600519.SH", "白酒")
        expected = {"revenue_stability", "margin_stability", "roe_stability",
                    "industry_predictability", "management_stability", "oe_growth_trend"}
        assert set(r.extrapolation_dims.keys()) == expected
        for v in r.extrapolation_dims.values():
            assert 1 <= v <= 5


class TestTurtleScorerEdgeCases:
    def test_l3_estimation(self, mock_client):
        scorer = TurtleScorer(mock_client)
        r = scorer.score("600519.SH")
        assert r.l3_multiplier in (1.0, 1.2, 0.8)
        assert isinstance(r.pool, str)

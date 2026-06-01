"""Unit tests for Turtle scoring pipeline."""

from unittest.mock import MagicMock, patch, PropertyMock

import pandas as pd
import pytest

from src.calculator.turtle_strategy.oe_calculator import OECalculator, OECalculationResult
from src.calculator.turtle_strategy.pr_calculator import PRCalculator, PRCalculationResult
from src.calculator.turtle_strategy.l5_calculator import L5Calculator, L5Result
from src.calculator.turtle_strategy.scoring import TurtleScorer, FinalScore
from src.data_pool.bundle import StockDataBundle


@pytest.fixture
def mock_bundle(real_tushare_data):
    """用真实 Tushare 数据快照构建 StockDataBundle mock。"""
    d = real_tushare_data["600519.SH"]
    bundle = StockDataBundle(
        ts_code="600519.SH",
        name="贵州茅台",
        industry="白酒",
        stock_basic=pd.DataFrame(d["stock_basic"]),
        fina_audit=pd.DataFrame(d["fina_audit"]),
        daily=pd.DataFrame(d["daily"]),
        daily_basic=pd.DataFrame(d["daily_basic"]),
        fina_indicator=pd.DataFrame(d["fina_indicator"]),
        income=pd.DataFrame(d["income"]),
        balancesheet=pd.DataFrame(d["balancesheet"]),
        cashflow=pd.DataFrame(d["cashflow"]),
        dividend=pd.DataFrame(d["dividend"]),
        repurchase=pd.DataFrame(),
        pledge_stat=pd.DataFrame(d["pledge_stat"]),
    )
    return bundle


class TestOECalculator:
    def test_basic_calculation(self, mock_bundle):
        oe = OECalculator(mock_bundle)
        r = oe.calculate("600519.SH", "白酒")
        assert isinstance(r, OECalculationResult)
        assert r.industry_prior == 0.45  # consumer_staples
        assert len(r.oe_cf_values) > 0

    def test_maintenance_coefficient(self, mock_bundle):
        oe = OECalculator(mock_bundle)
        r = oe.calculate("600519.SH", "白酒")
        # Consumer staples prior=0.45, with asset intensity factor
        assert 0.40 <= r.maintenance_coefficient <= 0.70


class TestPRCalculator:
    def test_basic_calculation(self, mock_bundle):
        pr = PRCalculator(mock_bundle)
        r = pr.calculate("600519.SH", "白酒")
        assert isinstance(r, PRCalculationResult)
        assert r.oe_cf_median > 0
        # v0.19: PR >= 0 with new formula
        assert r.pr_pct >= 0

    def test_starting_score_map(self, mock_bundle):
        pr = PRCalculator(mock_bundle)
        r = pr.calculate("600519.SH", "白酒")
        if r.pr_pct >= 12:
            assert r.starting_score == 20
        elif r.pr_pct >= 8:
            assert r.starting_score == 15
        elif r.pr_pct >= 5:
            assert r.starting_score == 10
        # else: starting_score could be 0


class TestL5Calculator:
    def test_basic_calculation(self, mock_bundle):
        l5 = L5Calculator(mock_bundle)
        r = l5.calculate("600519.SH", "白酒")
        assert isinstance(r, L5Result)
        assert r.extrapolation_total > 0
        assert r.l5_score <= 25

    def test_industry_predictability(self, mock_bundle):
        l5 = L5Calculator(mock_bundle)
        r = l5.calculate("600519.SH", "白酒")
        # 白酒 → 消费 → score=5 in YAML
        assert r.extrapolation_dims.get("industry_predictability", 0) >= 3


class TestTurtleScorer:
    def test_full_pipeline(self, mock_bundle):
        scorer = TurtleScorer(mock_bundle)
        r = scorer.score("600519.SH")
        assert isinstance(r, FinalScore)
        assert "茅台" in r.name  # 真实数据: 贵州茅台
        assert r.pool in ("核心池", "观察池", "备选池")

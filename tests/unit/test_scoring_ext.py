"""Extended edge case tests for calculators and LLM modules."""

from unittest.mock import MagicMock
import pandas as pd
import pytest

from src.turtle.calculator.oe_calculator import OECalculator
from src.turtle.calculator.pr_calculator import PRCalculator
from src.turtle.calculator.l5_calculator import L5Calculator
from src.turtle.calculator.scoring import TurtleScorer, FinalScore
from src.core.data.pool.bundle import StockDataBundle


@pytest.fixture
def mock_bundle(real_tushare_data):
    """用真实 Tushare 数据快照构建 StockDataBundle。"""
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


def _make_bundle(**overrides) -> StockDataBundle:
    """构建 StockDataBundle with overrides。"""
    return StockDataBundle(
        ts_code="t",
        name="test",
        industry="白酒",
        cashflow=overrides.get("cashflow", pd.DataFrame()),
        income=overrides.get("income", pd.DataFrame()),
        balancesheet=overrides.get("balancesheet", pd.DataFrame()),
        stock_basic=overrides.get("stock_basic", pd.DataFrame([{"name": "test", "industry": "白酒", "list_date": "20010101"}])),
        fina_audit=overrides.get("fina_audit", pd.DataFrame()),
        daily=overrides.get("daily", pd.DataFrame()),
        daily_basic=overrides.get("daily_basic", pd.DataFrame()),
        fina_indicator=overrides.get("fina_indicator", pd.DataFrame([{"roe": 25, "grossprofit_margin": 60}])),
        dividend=overrides.get("dividend", pd.DataFrame()),
        repurchase=overrides.get("repurchase", pd.DataFrame()),
        pledge_stat=overrides.get("pledge_stat", pd.DataFrame()),
    )


class TestOEEdgeCases:
    def test_empty_data_graceful(self):
        bundle = _make_bundle(
            cashflow=pd.DataFrame(),
            income=pd.DataFrame(),
        )
        oe = OECalculator(bundle)
        from src.turtle.calculator.oe_calculator import OECalculationResult
        r = oe.calculate("000001.SZ")
        assert isinstance(r, OECalculationResult)
        assert len(r.oe_cf_values) == 0

    def test_highly_stable_oe_trusted(self):
        bundle = _make_bundle(
            cashflow=pd.DataFrame([
                {"ts_code": "t", "end_date": f"202{d}1231", "n_cashflow_act": 1000, "c_pay_acq_const_fiolta": 50}
                for d in range(4, -1, -1)
            ]),
            income=pd.DataFrame([
                {"ts_code": "t", "end_date": f"202{d}1231", "n_income": 950, "total_revenue": 5000}
                for d in range(4, -1, -1)
            ]),
        )
        oe = OECalculator(bundle)
        r = oe.calculate("t", "白酒")
        # Stable OE with good profit ratio → trusted or questionable (not unreliable)
        assert r.quality_label in ("\U0001f7e2 可信", "\U0001f7e1 存疑")

    @pytest.mark.skip(reason="Mock OE calculation needs more complete BS data setup")
    def test_negative_oe_cagr(self):
        values = [500, 400, 300, 200, 100]
        bundle = _make_bundle(
            cashflow=pd.DataFrame([
                {"ts_code": "t", "end_date": f"202{d}1231", "n_cashflow_act": v, "c_pay_acq_const_fiolta": 10}
                for d, v in zip(range(4, -1, -1), values)
            ]),
            income=pd.DataFrame([
                {"ts_code": "t", "end_date": f"202{d}1231", "n_income": 200, "total_revenue": 1000}
                for d in range(4, -1, -1)
            ]),
            balancesheet=pd.DataFrame([
                {"ts_code": "t", "end_date": f"202{d}1231", "fix_assets": 100, "money_cap": 200,
                 "st_borrow": 0, "lt_borrow": 0, "bonds_payable": 0}
                for d in range(4, -1, -1)
            ]),
        )
        oe = OECalculator(bundle)
        r = oe.calculate("t")
        assert r.oe_cf_cagr_3y < 0, f"Expected negative CAGR, got {r.oe_cf_cagr_3y}"
        assert r.oe_cf_values, "OE values should not be empty"


class TestPRCalculatorEdgeCases:
    def test_zero_market_cap(self):
        bundle = _make_bundle(
            cashflow=pd.DataFrame([
                {"ts_code": "t", "end_date": f"202{d}1231", "n_cashflow_act": 1000, "c_pay_acq_const_fiolta": 50}
                for d in range(4, -1, -1)
            ]),
            income=pd.DataFrame([
                {"ts_code": "t", "end_date": f"202{d}1231", "n_income": 950, "total_revenue": 5000}
                for d in range(4, -1, -1)
            ]),
            daily_basic=pd.DataFrame([{
                "ts_code": "t", "trade_date": "20241231", "pe": 10, "pb": 2, "ps": 2,
                "dv_ratio": 2, "turnover_rate": 3, "total_mv": 0, "total_share": 10000,
            }]),
            dividend=pd.DataFrame([{
                "ts_code": "t", "end_date": "20241231", "cash_div_tax": 10, "div_proc": "实施"
            }]),
        )
        pr = PRCalculator(bundle)
        r = pr.calculate("t", "白酒")
        assert r.pr_pct == 0.0


class TestL5CalculatorEdgeCases:
    def test_downside_buffer_populated(self, mock_bundle):
        """v0.23: 下行缓冲详情应有3项: 资产底价/股息托底/回购支撑。"""
        l5 = L5Calculator(mock_bundle)
        r = l5.calculate("600519.SH", "白酒")
        # 验证新的下行缓冲结构
        assert len(r.downside_buffer_details) == 3
        detail_ids = {d["id"] for d in r.downside_buffer_details}
        assert detail_ids == {"asset_floor", "dividend_anchor", "buyback_support"}
        for d in r.downside_buffer_details:
            assert 0 <= d["score"] <= 2
            assert isinstance(d["label"], str)


class TestTurtleScorerEdgeCases:
    def test_l3_additive_scoring(self, mock_bundle):
        """v0.23: L3 十二维加法评分 (0-30pt)。"""
        scorer = TurtleScorer(mock_bundle)
        r = scorer.score("600519.SH")
        # v0.23: L3 是加法得分, 不是乘数
        assert hasattr(r, 'l3_score')
        assert 0 <= r.l3_score <= 30
        assert r.l3_level in ("优", "良", "中", "差", "")
        # 验证十二维详情
        assert len(r.l3_dim_scores) == 12
        for dim_id, dim_info in r.l3_dim_scores.items():
            assert 0 <= dim_info["score"] <= 2
            assert dim_info["group"] in ("盈利能力", "成熟度", "资本纪律", "治理")
        assert isinstance(r.pool, str)

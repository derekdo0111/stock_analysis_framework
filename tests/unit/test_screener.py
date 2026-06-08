"""Unit tests for screener: HardGate, L2, Classifier."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.turtle.screening.hard_gate import HardGateChecker, HardGateResult
from src.turtle.screening.l2_screener import L2Screener, L2ScoreResult
from src.turtle.screening.classifier import CompanyClassifier, ClassifyResult


@pytest.fixture
def mock_client():
    c = MagicMock()
    # Default: return empty DataFrames
    c.stock_basic.return_value = pd.DataFrame()
    c.fina_audit.return_value = pd.DataFrame()
    c.daily.return_value = pd.DataFrame()
    c.daily_basic.return_value = pd.DataFrame()
    c.fina_indicator.return_value = pd.DataFrame()
    c.income.return_value = pd.DataFrame()
    c.cashflow.return_value = pd.DataFrame()
    c.balancesheet.return_value = pd.DataFrame()
    c.dividend.return_value = pd.DataFrame()
    c.pledge_stat.return_value = pd.DataFrame()
    return c


class TestHardGate:
    def test_pass_clean_stock(self, mock_client):
        """Clean stock passes all gates."""
        mock_client.stock_basic.return_value = pd.DataFrame([{
            "ts_code": "600519.SH", "name": "贵州茅台", "industry": "白酒",
            "list_date": "20010827",
        }])
        mock_client.fina_audit.return_value = pd.DataFrame([{
            "ts_code": "600519.SH", "audit_result": "标准无保留意见",
            "audit_agency": "立信", "ann_date": "20250401",
        }])
        mock_client.daily.return_value = pd.DataFrame([
            {"trade_date": "20250501", "close": 1500},
            {"trade_date": "20250530", "close": 1520},
        ])

        checker = HardGateChecker(mock_client)
        r = checker.check("600519.SH")
        assert r.passed is True

    def test_veto_audit_opinion(self, mock_client):
        """Bad audit opinion triggers veto."""
        mock_client.fina_audit.return_value = pd.DataFrame([{
            "ts_code": "000001.SZ", "audit_result": "保留意见",
        }])
        checker = HardGateChecker(mock_client)
        r = checker.check("000001.SZ")
        assert r.passed is False
        assert "审计" in r.veto_reason

    def test_veto_st(self, mock_client):
        """ST stock triggers veto."""
        mock_client.stock_basic.return_value = pd.DataFrame([{
            "ts_code": "000004.SZ", "name": "*ST国华",
        }])
        checker = HardGateChecker(mock_client)
        r = checker.check("000004.SZ")
        assert r.passed is False
        assert "ST" in r.veto_reason

    def test_veto_manual_blacklist(self, mock_client):
        """Manual blacklist triggers veto."""
        checker = HardGateChecker(mock_client)
        checker._rules.hard_gate.manual_blacklist.ts_codes = ["999999.SZ"]
        r = checker.check("999999.SZ")
        assert r.passed is False

    def test_batch_check(self, mock_client):
        checker = HardGateChecker(mock_client)
        results = checker.check_batch(["600519.SH", "000001.SZ"])
        assert len(results) == 2
        assert all(isinstance(r, HardGateResult) for r in results)


class TestL2Screener:
    def test_score_good_stock(self, mock_client):
        """Good financials produce a decent score."""
        mock_client.fina_indicator.return_value = pd.DataFrame([{
            "ts_code": "600519.SH", "roe": 38.4, "grossprofit_margin": 91.9,
            "debt_to_assets": 25.0, "cf_sales": 0.5,
        }])
        mock_client.daily_basic.return_value = pd.DataFrame([{
            "ts_code": "600519.SH", "pe": 20, "pb": 5, "ps": 3,
            "dv_ratio": 2.5, "turnover_rate": 3,
        }])
        screener = L2Screener(mock_client)
        r = screener.score("600519.SH", "茅台")
        assert r.total > 5
        assert not r.eliminated

    def test_roe_below_hard_gate(self, mock_client):
        """ROE < 5% triggers elimination."""
        mock_client.fina_indicator.return_value = pd.DataFrame([{
            "ts_code": "000001.SZ", "roe": 2.0,
        }])
        screener = L2Screener(mock_client)
        r = screener.score("000001.SZ")
        assert r.eliminated
        assert "ROE" in r.eliminate_reason

    def test_dividend_zero_eliminates(self, mock_client):
        """股息率=0 triggers elimination."""
        mock_client.fina_indicator.return_value = pd.DataFrame([{
            "ts_code": "test", "roe": 20, "grossprofit_margin": 50, "debt_to_assets": 30,
        }])
        mock_client.daily_basic.return_value = pd.DataFrame([{
            "ts_code": "test", "pe": 15, "pb": 2, "ps": 1,
            "dv_ratio": 0, "turnover_rate": 3,
        }])
        screener = L2Screener(mock_client)
        r = screener.score("test")
        assert r.eliminated


class TestClassifier:
    def test_standard_consumer(self, mock_client):
        mock_client.stock_basic.return_value = pd.DataFrame([{
            "ts_code": "600519.SH", "name": "贵州茅台", "industry": "白酒",
        }])
        cls = CompanyClassifier(mock_client)
        r = cls.classify("600519.SH")
        assert r.category == "STANDARD_CONSUMER"
        assert r.eligible

    def test_financial_excluded(self, mock_client):
        mock_client.stock_basic.return_value = pd.DataFrame([{
            "ts_code": "000001.SZ", "name": "平安银行", "industry": "银行",
        }])
        cls = CompanyClassifier(mock_client)
        r = cls.classify("000001.SZ")
        assert r.category == "FINANCIAL"
        assert not r.eligible

    def test_cyclical_excluded(self, mock_client):
        mock_client.stock_basic.return_value = pd.DataFrame([{
            "ts_code": "600019.SH", "name": "宝钢股份", "industry": "钢铁",
        }])
        cls = CompanyClassifier(mock_client)
        r = cls.classify("600019.SH")
        assert r.category == "CYCLICAL"
        assert not r.eligible

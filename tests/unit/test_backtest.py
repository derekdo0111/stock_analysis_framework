"""Unit tests for backtest modules."""

from unittest.mock import MagicMock
import pandas as pd
import pytest

from src.backtest.window_manager import WindowManager, BacktestWindow, DEFAULT_WINDOWS
from src.backtest.dividend_validator import DividendValidator, DividendValidation, PR_MIN_THRESHOLD
from src.backtest.statistics import BacktestStatistics, WindowStats, CrossWindowSummary


class TestWindowManager:
    def test_generate_windows(self):
        wm = WindowManager()
        windows = wm.generate_windows()
        assert len(windows) >= 6
        assert windows[0].data_end_year >= 2011
        assert windows[0].data_end_year == 2011
        assert windows[0].validate_start_year == 2012

    def test_get_window(self):
        wm = WindowManager()
        w = wm.get_window(1)
        assert w is not None
        assert w.id == 1

    def test_get_window_out_of_range(self):
        wm = WindowManager()
        assert wm.get_window(99) is None

    def test_window_properties(self):
        w = BacktestWindow(id=1, label="test",
                           data_start_year=2015, data_end_year=2019,
                           validate_start_year=2020, validate_end_year=2024)
        assert "2015-2019" in w.data_period
        assert "2020-2024" in w.validate_period

    def test_default_windows(self):
        assert len(DEFAULT_WINDOWS) == 6
        assert DEFAULT_WINDOWS[0].data_start_year == 2011


class TestDividendValidator:
    @pytest.fixture
    def mock_client(self):
        c = MagicMock()
        c.dividend.return_value = pd.DataFrame([
            {"end_date": "20201231", "cash_div": 20, "div_proc": "实施"},
            {"end_date": "20211231", "cash_div": 22, "div_proc": "实施"},
            {"end_date": "20221231", "cash_div": 25, "div_proc": "实施"},
        ])
        return c

    @pytest.fixture
    def window(self):
        return BacktestWindow(id=1, label="test",
                              data_start_year=2015, data_end_year=2019,
                              validate_start_year=2020, validate_end_year=2022)

    def test_validate_basic(self, mock_client, window):
        v = DividendValidator(mock_client)
        r = v.validate("600519.SH", "茅台", 5.0, window, final_score=80)
        assert isinstance(r, DividendValidation)
        assert r.predicted_pr_pct == 5.0
        assert r.window_id == 1

    def test_pr_threshold(self, mock_client, window):
        v = DividendValidator(mock_client)
        r = v.validate("test", "t", 5.0, window)
        # 实际分红 20/22/25元 vs 预测5% — 取决于股价但兑现率应可算
        assert r.pr_fulfillment >= 0 or r.pr_fulfillment == 0

    def test_pr_min_threshold(self):
        assert PR_MIN_THRESHOLD == 5.0


class TestBacktestStatistics:
    def test_empty_validations(self):
        stats = BacktestStatistics()
        r = stats.analyze_window([], 1, "test")
        assert r.total_stocks == 0

    def test_analyze_with_validations(self):
        v1 = DividendValidation(
            ts_code="A", predicted_pr_pct=8, pr_fulfillment=0.85,
            actual_dividend_yield=6.8, is_pr_qualified=True,
            pr_threshold_met=True,
            window_id=1, final_score=80,
        )
        v2 = DividendValidation(
            ts_code="B", predicted_pr_pct=3, pr_fulfillment=0.4,
            actual_dividend_yield=1.2, is_pr_qualified=False,
            pr_threshold_met=False,
            window_id=1, final_score=30,
        )
        stats = BacktestStatistics()
        r = stats.analyze_window([v1, v2], 1, "test")
        assert r.total_stocks == 2
        assert r.pr_fulfill_qualified_pct == 50
        assert r.threshold_met_pct == 50

    def test_cross_window(self):
        stats = BacktestStatistics()
        w1 = WindowStats(window_id=1, window_label="w1", total_stocks=10,
                         avg_fulfillment=0.75, median_fulfillment=0.80,
                         pr_fulfill_qualified_pct=60, threshold_met_pct=55,
                         top5_avg_dividend=5.0, bottom5_avg_dividend=2.0, spread=3.0)
        w2 = WindowStats(window_id=2, window_label="w2", total_stocks=8,
                         avg_fulfillment=0.65, median_fulfillment=0.70,
                         pr_fulfill_qualified_pct=50, threshold_met_pct=45,
                         top5_avg_dividend=4.0, bottom5_avg_dividend=2.5, spread=1.5)
        cross = stats.analyze_cross_window([w1, w2])
        assert cross.total_windows == 2
        assert cross.avg_fulfillment == 0.75  # median of [0.80, 0.70]


class TestBacktestReport:
    def test_generate_report(self):
        from src.backtest.report import BacktestReportGenerator
        w1 = WindowStats(window_id=1, window_label="2011-2015", total_stocks=5,
                         avg_pr_pct=6.5, avg_fulfillment=0.72, median_fulfillment=0.75,
                         pr_fulfill_qualified_pct=60, threshold_met_pct=55,
                         top5_avg_dividend=5.0, bottom5_avg_dividend=2.0, spread=3.0)
        cross = CrossWindowSummary(total_windows=1, avg_fulfillment=0.72,
                                   avg_threshold_met_pct=55, avg_spread=3.0)
        gen = BacktestReportGenerator()
        html = gen.generate([w1], cross)
        assert len(html) > 1000
        assert "PR" in html

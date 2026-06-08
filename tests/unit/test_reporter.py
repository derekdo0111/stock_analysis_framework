"""Tests for report generator and transformer."""

import tempfile
from pathlib import Path
from datetime import date

import pytest

from src.turtle.reporter.report_generator import ReportGenerator
from src.turtle.calculator.scoring import FinalScore
from src.turtle.llm.orchestrator import OrchestrationResult
from src.turtle.llm.analysis_agent import AnalysisResult
from src.turtle.llm.verification_agent import VerificationResult
from src.core.data.pool.transformer.tushare_transformer import (
    tushare_row_to_model,
    tushare_df_to_models,
    _parse_date,
)
from src.core.data.pool.schema.models import StockBasic


class TestReportGenerator:
    @pytest.fixture
    def fs(self):
        return FinalScore(
            ts_code="600519.SH", name="test", l2_score=15, l3_multiplier=1.0,
            l4_score=20, l5_score=18, raw_total=53, final_score=53,
            pool="观察池", pr_pct=6.5, oe_quality="\U0001f7e2 可信",
            position_pct=8, business_model="良",
        )

    def test_generate_bare(self, fs):
        gen = ReportGenerator()
        html = gen.generate(fs)
        assert len(html) > 2000
        assert "test" in html
        assert "600519.SH" in html
        assert "观察池" in html

    def test_generate_with_analysis(self, fs):
        analysis = AnalysisResult(
            ts_code="600519.SH", success=True, qualitative_total=30,
            business_model="优", module_details=[
                {"module": "test", "score": 4, "confidence": "high",
                 "evidence": "evidence text", "uncertainty": ""},
            ],
        )
        orch = OrchestrationResult(
            ts_code="600519.SH", analysis=analysis, verification=None,
            final_score=fs, retries=0, final_verdict="通过",
        )
        gen = ReportGenerator()
        html = gen.generate(fs, orch)
        assert "evidence text" in html
        assert "test" in html

    def test_generate_with_full_pipeline(self, fs):
        analysis = AnalysisResult(
            ts_code="600519.SH", success=True, qualitative_total=34,
            business_model="优",
            module_details=[
                {"module": "m1", "score": 5, "confidence": "high",
                 "evidence": "ev", "uncertainty": ""},
            ],
            red_flags=["flag1"],
        )
        verification = VerificationResult(
            ts_code="600519.SH", success=True, overall_verdict="部分修正",
            fact_check_pass_rate=80, executive_summary="summary",
            fact_checks=[
                {"module": "m1", "claim": "c1", "verified": True, "evidence": "ev1"},
                {"module": "m1", "claim": "c2", "verified": False, "severity": "WARNING",
                 "evidence": "ev2"},
            ],
            data_issues=[{"audit_program": "p1", "finding": "f1", "severity": "WARNING"}],
            consistency_flags=[],
        )
        orch = OrchestrationResult(
            ts_code="600519.SH", analysis=analysis, verification=verification,
            final_score=fs, retries=1, final_verdict="部分修正",
        )
        gen = ReportGenerator()
        html = gen.generate(fs, orch)
        assert "flag1" in html
        assert "summary" in html
        assert "部分修正" in html

    def test_save_to_file(self, fs):
        gen = ReportGenerator()
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            path = f.name
        try:
            html = gen.save(fs, path)
            assert Path(path).exists()
            content = Path(path).read_text(encoding="utf-8")
            assert len(content) > 1000
        finally:
            Path(path).unlink(missing_ok=True)

    def test_generate_with_oe_details(self, fs):
        gen = ReportGenerator()
        oe_details = {
            "mc": 0.45, "oe_cf_median": "100", "oe_cf_mean": "95",
            "oe_cf_cv": "5%", "oe_cf_cagr": 3.5,
            "oe_income_median": "90", "profit_to_cash": 0.78,
            "oe_to_profit": 0.85,
            "industry_prior": 0.45, "capex_rev_pct": 2.5,
            "fixed_at": 6.0, "dep_rev_pct": 1.5, "asset_score": 0.45,
        }
        html = gen.generate(fs, oe_details=oe_details)
        assert "0.45" in html


class TestTushareTransformer:
    def test_parse_date_int(self):
        assert _parse_date(20010827) == date(2001, 8, 27)
        assert _parse_date("20241231") == date(2024, 12, 31)
        assert _parse_date(None) is None
        assert _parse_date("invalid") is None

    def test_row_to_model(self):
        row = {
            "ts_code": "600519.SH", "name": "test", "industry": "白酒",
            "list_date": 20010827,
        }
        model = tushare_row_to_model(row, StockBasic)
        assert model.ts_code == "600519.SH"
        assert model.list_date == date(2001, 8, 27)
        assert model.raw_tushare_data["list_date"] == 20010827

    def test_row_to_model_no_raw(self):
        row = {"ts_code": "test", "name": "t"}
        model = tushare_row_to_model(row, StockBasic, preserve_raw=False)
        assert model.raw_tushare_data == {}

    def test_df_to_models(self):
        import pandas as pd
        df = pd.DataFrame([
            {"ts_code": "A", "name": "a", "list_date": "20200101"},
            {"ts_code": "B", "name": "b", "list_date": "20200601"},
        ])
        models, errors = tushare_df_to_models(df, StockBasic)
        assert len(models) == 2
        assert len(errors) == 0

    def test_df_to_models_errors(self):
        import pandas as pd
        df = pd.DataFrame([{"bad_field": 1}])
        models, errors = tushare_df_to_models(df, StockBasic)
        assert len(errors) > 0

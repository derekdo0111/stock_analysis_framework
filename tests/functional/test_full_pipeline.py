"""
功能测试 — 全管线端到端 (真实Token)。

验证: 选股→HardGate→L2→分类→OE→PR→L5→打分→Agent降级→报告 完整链路。
"""

from __future__ import annotations

import os
import tempfile

import pytest

TS = "600519.SH"
TOKEN_AVAILABLE = bool(os.environ.get("TUSHARE_TOKEN"))

pytestmark = pytest.mark.skipif(
    not TOKEN_AVAILABLE,
    reason="TUSHARE_TOKEN not set.",
)


class TestFullPipeline:
    def test_complete_flow_quant_only(self):
        """完整管流量化层面 (无需LLM Key)."""
        from src.data_fetcher.tushare_client import TushareClient
        from src.screener.hard_gate import HardGateChecker
        from src.screener.l2_screener import L2Screener
        from src.screener.classifier import CompanyClassifier
        from src.calculator.turtle_strategy.scoring import TurtleScorer
        from src.reporter.report_generator import ReportGenerator

        client = TushareClient()

        # HardGate
        hg = HardGateChecker(client)
        r = hg.check(TS)
        assert r.passed, f"HardGate failed: {r.veto_reason}"

        # L2
        l2 = L2Screener(client)
        r2 = l2.score(TS)
        assert not r2.eliminated, f"L2 eliminated: {r2.eliminate_reason}"

        # 分类
        cls = CompanyClassifier(client)
        r3 = cls.classify(TS)
        assert r3.eligible, f"Not eligible: {r3.category}"

        # 打分
        scorer = TurtleScorer(client)
        r4 = scorer.score(TS)
        assert r4.is_valid
        assert r4.pool in ("核心池", "观察池", "备选池")
        assert r4.l2_score >= 0
        assert r4.final_score >= 0

        # 报告
        gen = ReportGenerator()
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            html = gen.save(r4, path)
            assert len(html) > 2000
            assert TS in html
        finally:
            os.unlink(path)

"""Unit tests for LLM agents — fallback path (no API key needed)."""

from unittest.mock import MagicMock, patch

import pytest

from src.turtle.llm.analysis_agent import AnalysisAgent, AnalysisResult
from src.turtle.llm.verification_agent import VerificationAgent, VerificationResult
from src.turtle.llm.orchestrator import AgentOrchestrator
from src.turtle.calculator.scoring import FinalScore


@pytest.fixture
def sample_final_score() -> FinalScore:
    return FinalScore(
        ts_code="600519.SH",
        name="贵州茅台",
        l2_score=10.5,
        l3_multiplier=1.0,
        l4_score=5.0,
        l5_score=10.0,
        raw_total=25.5,
        final_score=25.5,
        pool="观察池",
        pr_pct=3.5,
        oe_quality="🟡 存疑",
        position_pct=5.0,
        business_model="良",
    )


class TestAnalysisAgentFallback:
    """Without LLM API key, analysis agent falls back to default scoring."""

    def test_fallback_without_key(self, sample_final_score):
        agent = AnalysisAgent(client=None)
        result = agent.analyze(sample_final_score)
        assert isinstance(result, AnalysisResult)
        assert not result.success
        assert result.qualitative_total > 0
        assert len(result.module_scores) == 9
        assert result.business_model == "良"

    def test_fallback_uses_l2_basis(self, sample_final_score):
        agent = AnalysisAgent(client=None)
        result = agent.analyze(sample_final_score)
        # L2=10.5/20 → base≈2.625 → 9 modules × 2.625 = ~23.6
        assert 20 <= result.qualitative_total <= 30


class TestVerificationAgentFallback:
    """Without LLM API key, verification agent returns reliable-info."""

    def test_fallback_without_key(self):
        analysis = AnalysisResult(
            ts_code="600519.SH",
            qualitative_total=28,
            business_model="良",
        )
        agent = VerificationAgent(client=None)
        result = agent.verify(analysis)
        assert isinstance(result, VerificationResult)
        assert not result.success
        assert result.overall_verdict == "不可靠"


class TestOrchestratorFallback:
    """Orchestrator handles missing LLM gracefully."""

    def test_fallback_without_key(self, sample_final_score):
        orch = AgentOrchestrator(client=None)
        result = orch.run(sample_final_score)
        assert result.analysis is not None
        assert not result.analysis.success
        assert result.final_verdict == "不可靠"


class TestLLMConfig:
    def test_not_configured_by_default(self):
        import os
        # Should be false unless env vars are set
        from src.core.llm.client import LLMConfig
        has_openai = bool(os.environ.get("OPENAI_API_KEY"))
        has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
        if not has_openai and not has_anthropic:
            assert not LLMConfig.is_configured()

"""Extended LLM tests — prompt builders, config, orchestrator flow (no API key needed)."""

import os
from unittest.mock import MagicMock, patch
import pytest

from src.llm.client import LLMConfig, LLMClient, LLMError
from src.llm.analysis_agent import AnalysisAgent, AnalysisResult
from src.llm.verification_agent import VerificationAgent, VerificationResult
from src.llm.orchestrator import AgentOrchestrator, OrchestrationResult
from src.calculator.turtle_strategy.scoring import FinalScore


@pytest.fixture
def fs():
    return FinalScore(
        ts_code="600519.SH", name="Test", l2_score=15, l3_multiplier=1.0,
        l4_score=20, l5_score=15, raw_total=50, final_score=50,
        pool="观察池", pr_pct=6.5, oe_quality="\U0001f7e2 可信",
        position_pct=8, business_model="良",
    )


class TestLLMConfig:
    def test_not_configured_returns_false(self):
        if not os.environ.get("DEEPSEEK_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
            assert not LLMConfig.is_configured()

    def test_default_model_is_deepseek(self):
        assert LLMConfig.model() == "deepseek-chat"

    def test_provider_from_env(self):
        # If no env set, provider() returns ""
        provider = LLMConfig.provider()
        assert provider in ("", "deepseek", "openai", "anthropic")


class TestAnalysisAgentPrompt:
    """Test that system prompt is built correctly without needing API call."""

    def test_system_prompt_format(self):
        agent = AnalysisAgent(client=None)
        prompt = agent._build_system_prompt()
        assert "CFA" in prompt
        assert "证据链" in prompt
        assert "JSON" in prompt
        assert len(prompt) > 500

    def test_user_message_format(self, fs):
        agent = AnalysisAgent(client=None)
        msg = agent._build_user_message(fs, {"roe": 30})
        assert "600519.SH" in msg
        assert "roe" in msg
        assert "6.5%" in msg or "6.5" in msg

    def test_fallback_scoring(self, fs):
        agent = AnalysisAgent(client=None)
        result = agent.analyze(fs)
        assert not result.success
        assert len(result.module_scores) == 9
        assert all(0 < v <= 5 for v in result.module_scores.values())


class TestVerificationAgentPrompt:
    """Test verification prompt builders."""

    def test_system_prompt_format(self):
        agent = VerificationAgent(client=None)
        prompt = agent._build_system_prompt()
        assert "CPA" in prompt
        assert "审计" in prompt
        assert "JSON" in prompt

    def test_user_message_format(self):
        agent = VerificationAgent(client=None)
        analysis = AnalysisResult(
            ts_code="600519.SH", name="Test", qualitative_total=30,
            business_model="良", module_details=[
                {"module": "m1", "score": 4, "confidence": "high",
                 "evidence": "test evidence", "uncertainty": "none"},
            ],
        )
        msg = agent._build_user_message(analysis, {"roe": 30})
        assert "m1" in msg
        assert "test evidence" in msg

    def test_fallback_verification(self):
        agent = VerificationAgent(client=None)
        analysis = AnalysisResult(ts_code="test", qualitative_total=30)
        result = agent.verify(analysis)
        assert not result.success
        assert result.overall_verdict == "不可靠"


class TestOrchestratorFlow:
    def test_fallback_without_llm(self, fs):
        orch = AgentOrchestrator(client=None)
        result = orch.run(fs)
        assert isinstance(result, OrchestrationResult)
        assert result.final_verdict == "不可靠"
        assert result.analysis is not None
        assert not result.analysis.success

    def test_orchestration_result_structure(self, fs):
        analysis = AnalysisResult(ts_code="test", success=True, qualitative_total=30)
        verification = VerificationResult(ts_code="test", success=True,
                                          overall_verdict="通过",
                                          fact_check_pass_rate=90)
        result = OrchestrationResult(
            ts_code="test", name="test", final_score=fs,
            analysis=analysis, verification=verification,
            retries=0, final_verdict="通过",
        )
        assert result.final_verdict == "通过"
        assert result.analysis.qualitative_total == 30
        assert result.verification.fact_check_pass_rate == 90

"""LLM 智能层 — 双Agent分析+验证"""

from src.llm.client import LLMClient, LLMConfig, LLMError
from src.llm.analysis_agent import AnalysisAgent, AnalysisResult
from src.llm.verification_agent import VerificationAgent, VerificationResult
from src.llm.orchestrator import AgentOrchestrator, OrchestrationResult
from src.llm.cross_validation_agent import CrossValidationAgent, CrossValidationResult, Discrepancy
from src.llm.claim_types import (
    AnalysisClaim,
    VerifiedClaim,
    RevisedClaim,
    ClaimVerificationResult,
)
from src.llm.provider import LLMProvider, LLMResponse, DeepSeekProvider, OpenAIProvider, create_provider
from src.llm.manager import LLMManager
from src.llm.schema import AnalysisOutput, VerificationOutput, ModuleScore, VerificationItem
from src.llm.cache import LLMCache
from src.llm.prompt_builder import PromptBuilder

__all__ = [
    "LLMClient",
    "LLMConfig",
    "LLMError",
    "AnalysisAgent",
    "AnalysisResult",
    "VerificationAgent",
    "VerificationResult",
    "AgentOrchestrator",
    "OrchestrationResult",
    "CrossValidationAgent",
    "CrossValidationResult",
    "Discrepancy",
    "AnalysisClaim",
    "VerifiedClaim",
    "RevisedClaim",
    "ClaimVerificationResult",
    "LLMProvider",
    "LLMResponse",
    "DeepSeekProvider",
    "OpenAIProvider",
    "create_provider",
    "LLMManager",
    "AnalysisOutput",
    "VerificationOutput",
    "ModuleScore",
    "VerificationItem",
    "LLMCache",
    "PromptBuilder",
]

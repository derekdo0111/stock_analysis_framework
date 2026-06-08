"""LLM 智能层 — 向后兼容聚合导出 (v0.35)

新代码请直接从 src.core.llm 或 src.turtle.llm 导入。
"""

from src.core.llm.client import LLMClient, LLMConfig, LLMError
from src.turtle.llm.analysis_agent import AnalysisAgent, AnalysisResult
from src.turtle.llm.verification_agent import VerificationAgent, VerificationResult
from src.turtle.llm.orchestrator import AgentOrchestrator, OrchestrationResult
from src.turtle.llm.cross_validation_agent import CrossValidationAgent, CrossValidationResult, Discrepancy
from src.turtle.llm.claim_types import (
    AnalysisClaim,
    VerifiedClaim,
    RevisedClaim,
    ClaimVerificationResult,
)
from src.core.llm.provider import LLMProvider, LLMResponse, DeepSeekProvider, OpenAIProvider, create_provider
from src.core.llm.manager import LLMManager
from src.core.llm.cache import LLMCache
from src.turtle.llm.prompt_builder import PromptBuilder

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
    "LLMCache",
    "PromptBuilder",
]

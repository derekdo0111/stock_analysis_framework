"""LLM Schema — 分析/验证 Agent 输出的 Pydantic 硬校验模型。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ModuleScore(BaseModel):
    """分析 Agent 单个模块打分。"""
    module_name: str = Field(..., description="模块名称")
    score: float = Field(..., ge=0, le=10, description="0-10 分")
    evidence: str = Field(..., description="三段式证据链文本")


class AnalysisOutput(BaseModel):
    """分析 Agent 标准化输出 Schema。

    用于 Pydantic 硬校验，确保 LLM 输出格式正确。
    """
    ts_code: str = Field(..., description="股票代码")
    name: str = Field(default="", description="股票名称")
    overall_assessment: str = Field(default="", description="综合评估")
    modules: list[ModuleScore] = Field(default_factory=list, description="各模块打分")
    total_score: float = Field(default=0.0, ge=0, le=100, description="分析总分")
    confidence: str = Field(default="medium", description="置信度: high/medium/low")


class VerificationItem(BaseModel):
    """验证 Agent 单项审计程序结果。"""
    procedure_name: str = Field(..., description="审计程序名称")
    passed: bool = Field(default=True)
    severity: str = Field(default="INFO", description="严重度: INFO/WARNING/CRITICAL")
    finding: str = Field(default="", description="验证发现")
    evidence: str = Field(default="", description="验证依据")


class VerificationOutput(BaseModel):
    """验证 Agent 标准化输出 Schema。"""
    ts_code: str = Field(..., description="股票代码")
    items: list[VerificationItem] = Field(default_factory=list, description="审计程序结果")
    passed_count: int = Field(default=0, description="通过项数")
    warning_count: int = Field(default=0, description="WARNING 项数")
    critical_count: int = Field(default=0, description="CRITICAL 项数")
    summary: str = Field(default="", description="验证总结")


__all__ = [
    "ModuleScore",
    "AnalysisOutput",
    "VerificationItem",
    "VerificationOutput",
]

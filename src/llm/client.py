"""
LLM 客户端 — OpenAI / Anthropic 统一适配 + tenacity 重试 + 降级。

支持:
- OpenAI GPT-4o / GPT-4o-mini
- Anthropic Claude-3.5-Sonnet
- 自动选择可用provider (env var配置)
- 结构化输出（工具调用模式）
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class LLMError(Exception):
    """LLM 调用失败。"""


class LLMConfig:
    """LLM 配置从环境变量读取。"""

    @staticmethod
    def provider() -> str:
        return os.environ.get("LLM_PROVIDER", "").lower()  # "openai" | "anthropic" | ""

    @staticmethod
    def model() -> str:
        return os.environ.get("LLM_MODEL", "gpt-4o-mini")

    @staticmethod
    def api_key() -> str:
        key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or ""
        return key

    @staticmethod
    def is_configured() -> bool:
        return bool(LLMConfig.api_key())


class LLMClient:
    """统一 LLM 客户端 — 自动选择 OpenAI 或 Anthropic。"""

    def __init__(self, model: str | None = None):
        self._model = model or LLMConfig.model()
        self._provider = self._detect_provider()
        self._client = self._init_client()
        logger.info(f"LLM: {self._provider}/{self._model}")

    def _detect_provider(self) -> str:
        provider = LLMConfig.provider()
        if provider:
            return provider
        if os.environ.get("OPENAI_API_KEY"):
            return "openai"
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "anthropic"
        raise LLMError(
            "No LLM API key configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY."
        )

    def _init_client(self):
        if self._provider == "openai":
            from openai import OpenAI
            return OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        elif self._provider == "anthropic":
            from anthropic import Anthropic
            return Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        raise LLMError(f"Unknown provider: {self._provider}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((LLMError,)),
        reraise=True,
    )
    def chat(
        self,
        system_prompt: str,
        user_message: str,
        *,
        temperature: float = 0,
        max_tokens: int = 4096,
        response_format: dict | None = None,
    ) -> str:
        """发送 chat completion 请求。

        Args:
            system_prompt: 系统提示词
            user_message: 用户消息（含分析数据）
            temperature: 创意程度 (0=确定性输出)
            max_tokens: 最大输出token
            response_format: OpenAI JSON mode 配置 (Anthropic 忽略)
        """
        try:
            if self._provider == "openai":
                return self._chat_openai(system_prompt, user_message, temperature, max_tokens, response_format)
            else:
                return self._chat_anthropic(system_prompt, user_message, temperature, max_tokens)
        except Exception as e:
            msg = str(e)
            if "429" in msg or "rate" in msg.lower():
                raise LLMError(f"Rate limited: {msg}") from e
            if "401" in msg or "403" in msg:
                raise LLMError(f"API key invalid: {msg}") from e
            raise LLMError(f"LLM call failed: {msg}") from e

    def _chat_openai(
        self, system: str, user: str, temperature: float, max_tokens: int, response_format: dict | None
    ) -> str:
        kwargs = dict(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if response_format:
            kwargs["response_format"] = response_format
        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content

    def _chat_anthropic(
        self, system: str, user: str, temperature: float, max_tokens: int
    ) -> str:
        resp = self._client.messages.create(
            model=self._model,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.content[0].text

    def chat_json(
        self,
        system_prompt: str,
        user_message: str,
        *,
        temperature: float = 0,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Chat 并解析为 JSON dict。

        对 OpenAI 使用 JSON mode，对 Anthropic 用纯文本+手动解析。
        """
        response_format = None
        if self._provider == "openai":
            response_format = {"type": "json_object"}

        text = self.chat(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )

        # 提取 JSON（处理可能的 markdown 代码块包装）
        text = text.strip()
        if text.startswith("```"):
            # 移除 markdown 代码块
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试从文本中提取 JSON
            import re
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            logger.warning(f"Failed to parse JSON from LLM response (first 200 chars): {text[:200]}")
            raise LLMError("LLM response is not valid JSON")

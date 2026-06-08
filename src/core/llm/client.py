"""
LLM 客户端 — DeepSeek / OpenAI / Anthropic 统一适配 + tenacity 重试 + 降级。

支持:
- DeepSeek V4 Pro / Flash (OpenAI 兼容 API, base_url=https://api.deepseek.com)
- OpenAI GPT-4o / GPT-4o-mini
- Anthropic Claude-3.5-Sonnet
- 自动选择可用 provider (env var配置)
- 结构化输出（JSON mode）
- Tool Calling 多轮对话 (chat_with_tools) — v0.27 新增
- 三模型独立配置 (检索/分析/验证) — v0.27 新增

用法:
    from src.core.llm.client import LLMClient, LLMConfig

    # 默认模型
    client = LLMClient()

    # 指定模型（如检索Agent用独立模型）
    client = LLMClient(model=LLMConfig.retrieval_model())
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
    """LLM 配置从环境变量读取。

    环境变量:
        LLM_PROVIDER: deepseek | openai | anthropic (默认自动检测)
        LLM_MODEL: 默认模型名 (默认 deepseek-chat)
        DEEPSEEK_API_KEY: DeepSeek API密钥
        OPENAI_API_KEY: OpenAI API密钥
        ANTHROPIC_API_KEY: Anthropic API密钥

        LLM_RETRIEVAL_MODEL: 商业检索Agent模型 (可选，默认同 LLM_MODEL)
        LLM_ANALYSIS_MODEL: 分析Agent模型 (可选，默认同 LLM_MODEL)
        LLM_VALIDATION_MODEL: 交叉验证Agent模型 (可选，默认同 LLM_MODEL)
    """

    @staticmethod
    def provider() -> str:
        """返回当前 provider: deepseek / openai / anthropic."""
        return os.environ.get("LLM_PROVIDER", "").lower()

    @staticmethod
    def model() -> str:
        """返回默认模型名，DeepSeek 默认 deepseek-chat (V4 Flash等效)。"""
        default = "deepseek-chat"
        return os.environ.get("LLM_MODEL", default)

    @staticmethod
    def retrieval_model() -> str:
        """Phase 3.5 商业检索Agent模型 (需要 tool calling)。"""
        return os.environ.get("LLM_RETRIEVAL_MODEL", LLMConfig.model())

    @staticmethod
    def analysis_model() -> str:
        """Phase 5a 分析Agent模型 (需要长篇写作)。"""
        return os.environ.get("LLM_ANALYSIS_MODEL", LLMConfig.model())

    @staticmethod
    def validation_model() -> str:
        """Phase 5b 交叉验证Agent模型 (需要严格 JSON)。"""
        return os.environ.get("LLM_VALIDATION_MODEL", LLMConfig.model())

    @staticmethod
    def api_key() -> str:
        key = (
            os.environ.get("DEEPSEEK_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("ANTHROPIC_API_KEY")
            or ""
        )
        return key

    @staticmethod
    def is_configured() -> bool:
        return bool(LLMConfig.api_key())


class LLMClient:
    """统一 LLM 客户端 — 自动检测 DeepSeek/OpenAI/Anthropic。

    优先级: LLM_PROVIDER 环境变量 > 自动检测 (DeepSeek > OpenAI > Anthropic)
    """

    # DeepSeek API 配置
    DEEPSEEK_BASE_URL = "https://api.deepseek.com"

    def __init__(self, model: str | None = None):
        self._model = model or LLMConfig.model()
        self._provider = self._detect_provider()
        self._client = self._init_client()
        logger.info(f"LLM: {self._provider}/{self._model}")

    def _detect_provider(self) -> str:
        provider = LLMConfig.provider()
        if provider:
            return provider
        # 自动检测
        if os.environ.get("DEEPSEEK_API_KEY"):
            return "deepseek"
        if os.environ.get("OPENAI_API_KEY"):
            return "openai"
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "anthropic"
        raise LLMError(
            "No LLM API key configured. "
            "Set DEEPSEEK_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY."
        )

    def _init_client(self):
        if self._provider in ("deepseek", "openai"):
            from openai import OpenAI

            if self._provider == "deepseek":
                return OpenAI(
                    api_key=os.environ["DEEPSEEK_API_KEY"],
                    base_url=self.DEEPSEEK_BASE_URL,
                )
            else:
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

        DeepSeek 和 OpenAI 使用 OpenAI 兼容接口，Anthropic 用独立接口。
        """
        try:
            if self._provider in ("deepseek", "openai"):
                return self._chat_openai_compatible(
                    system_prompt, user_message, temperature, max_tokens, response_format
                )
            else:
                return self._chat_anthropic(system_prompt, user_message, temperature, max_tokens)
        except Exception as e:
            msg = str(e)
            if "429" in msg or "rate" in msg.lower():
                raise LLMError(f"Rate limited: {msg}") from e
            if "401" in msg or "403" in msg:
                raise LLMError(f"API key invalid: {msg}") from e
            raise LLMError(f"LLM call failed: {msg}") from e

    def _chat_openai_compatible(
        self, system: str, user: str, temperature: float, max_tokens: int,
        response_format: dict | None,
    ) -> str:
        kwargs: dict[str, Any] = dict(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # DeepSeek 不支持 strict JSON mode，但支持普通 JSON 格式
        if response_format and self._provider != "deepseek":
            kwargs["response_format"] = response_format
        # DeepSeek: 用 system/user 提示词引导 JSON 输出即可
        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content

    def _chat_anthropic(
        self, system: str, user: str, temperature: float, max_tokens: int,
    ) -> str:
        resp = self._client.messages.create(
            model=self._model,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.content[0].text

    # ══════════════════════════════════════════════════════════
    # Tool Calling (v0.27 新增)
    # ══════════════════════════════════════════════════════════

    def chat_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[dict],
        tool_executor: Callable[[str, dict[str, Any]], str],
        *,
        temperature: float = 0.3,
        max_turns: int = 5,
        max_tokens: int = 4096,
    ) -> str:
        """多轮 tool calling 对话。

        LLM 可在推理过程中多次调用工具（如 web_search），
        每次调用结果会回传，直到模型输出最终文本。

        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            tools: 工具定义列表 (OpenAI/DeepSeek 格式)
            tool_executor: 工具执行回调 (tool_name, arguments) -> result_text
            temperature: 采样温度
            max_turns: 最大工具调用轮次 (防止无限循环)
            max_tokens: 每轮最大生成 token 数

        Returns:
            最终的模型文本响应

        Raises:
            LLMError: API 调用失败或超出最大轮次
        """
        if self._provider not in ("deepseek", "openai"):
            # Anthropic 暂不支持 tool calling 的直接模式，降级为单次调用
            logger.warning("Anthropic 暂不支持 tool calling，使用单次调用")
            return self.chat(
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        for turn in range(max_turns):
            try:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as e:
                msg = str(e)
                if "429" in msg or "rate" in msg.lower():
                    raise LLMError(f"Rate limited in tool calling: {msg}") from e
                raise LLMError(f"Tool calling failed: {msg}") from e

            choice = resp.choices[0]
            msg = choice.message

            # 如果有 tool_calls，执行工具并回传结果
            if msg.tool_calls:
                # 添加 assistant 消息（含 tool_calls）
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })

                # 执行每个 tool call
                for tc in msg.tool_calls:
                    func_name = tc.function.name
                    try:
                        func_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        func_args = {}

                    logger.info(f"  [tool] {func_name}({func_args.get('query', '')[:40]}...)")
                    result_text = tool_executor(func_name, func_args)

                    # 添加 tool 响应消息
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_text,
                    })

                continue  # 继续下一轮，让 LLM 处理工具结果

            # 无 tool_calls，返回最终文本
            return msg.content or ""

        raise LLMError(f"Tool calling 达到最大轮次 ({max_turns})，仍未获得最终响应")

    def chat_json(
        self,
        system_prompt: str,
        user_message: str,
        *,
        temperature: float = 0,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Chat 并解析为 JSON dict。"""
        # DeepSeek 不支持 strict json_object mode，但通过 prompt 引导即可
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

        # 提取 JSON（处理 markdown 代码块包装）
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            logger.warning(f"Failed to parse JSON (first 200 chars): {text[:200]}")
            raise LLMError("LLM response is not valid JSON")

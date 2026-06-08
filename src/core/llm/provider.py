"""LLM Provider 适配层 — 多平台统一接口 (DeepSeek/OpenAI/Anthropic)。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from loguru import logger


@dataclass
class LLMResponse:
    """LLM 调用统一返回格式。"""
    content: str
    model: str = ""
    usage: dict[str, int] | None = None     # {prompt_tokens, completion_tokens}
    finish_reason: str = ""
    raw: Any = None                          # Provider 原生响应


class LLMProvider(Protocol):
    """LLM Provider 协议接口。"""

    def chat(self, messages: list[dict[str, str]], **kwargs) -> LLMResponse:
        """发送对话请求。"""
        ...


class DeepSeekProvider:
    """DeepSeek API Provider (OpenAI-compatible)。"""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com/v1",
                 model: str = "deepseek-chat"):
        self._api_key = api_key
        self._base_url = base_url
        self._model = model

    def chat(self, messages: list[dict[str, str]], **kwargs) -> LLMResponse:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self._api_key, base_url=self._base_url)
            resp = client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=kwargs.get("temperature", 0.0),
                max_tokens=kwargs.get("max_tokens", 4096),
            )
            choice = resp.choices[0]
            return LLMResponse(
                content=choice.message.content or "",
                model=resp.model,
                usage={
                    "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                    "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
                },
                finish_reason=choice.finish_reason or "",
                raw=resp,
            )
        except Exception as e:
            logger.error(f"DeepSeek API 调用失败: {e}")
            raise


class OpenAIProvider:
    """OpenAI API Provider。"""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self._api_key = api_key
        self._model = model

    def chat(self, messages: list[dict[str, str]], **kwargs) -> LLMResponse:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self._api_key)
            resp = client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=kwargs.get("temperature", 0.0),
                max_tokens=kwargs.get("max_tokens", 4096),
            )
            choice = resp.choices[0]
            return LLMResponse(
                content=choice.message.content or "",
                model=resp.model,
                finish_reason=choice.finish_reason or "",
                raw=resp,
            )
        except Exception as e:
            logger.error(f"OpenAI API 调用失败: {e}")
            raise


def create_provider(
    name: str,
    api_key: str,
    **kwargs,
) -> LLMProvider:
    """工厂函数 — 根据名称创建 LLM Provider。

    Args:
        name: "deepseek" / "openai" / "anthropic"
        api_key: API Key
        **kwargs: 传递给具体 Provider 的参数

    Returns:
        LLMProvider 实例
    """
    providers = {
        "deepseek": DeepSeekProvider,
        "openai": OpenAIProvider,
    }

    cls = providers.get(name.lower())
    if cls is None:
        raise ValueError(f"不支持的 LLM Provider: {name}. 可选: {list(providers.keys())}")

    return cls(api_key=api_key, **kwargs)


__all__ = [
    "LLMProvider",
    "LLMResponse",
    "DeepSeekProvider",
    "OpenAIProvider",
    "create_provider",
]

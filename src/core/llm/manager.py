"""LLM Manager — 管理 LLM Provider 实例、配置和连接池。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from loguru import logger

from src.core.llm.client import LLMClient, LLMConfig
from src.core.llm.provider import LLMProvider, create_provider


@dataclass
class LLMManager:
    """LLM 实例管理器。

    管理多个 Provider 实例，支持按名称切换。

    Usage:
        manager = LLMManager()
        manager.add_provider("deepseek", api_key="sk-xxx")
        client = manager.get_client("deepseek")
        response = client.chat([{"role": "user", "content": "Hello"}])
    """

    _providers: dict[str, LLMProvider] = field(default_factory=dict)
    _clients: dict[str, LLMClient] = field(default_factory=dict)
    _default_name: str = "deepseek"

    def add_provider(
        self,
        name: str,
        api_key: str,
        *,
        model: str | None = None,
        base_url: str | None = None,
        set_default: bool = False,
    ) -> LLMProvider:
        """注册一个新的 LLM Provider。

        Args:
            name: Provider 名称 (e.g. "deepseek", "openai")
            api_key: API Key
            model: 模型名称
            base_url: API Base URL
            set_default: 是否设为默认 Provider

        Returns:
            创建的 Provider 实例
        """
        kwargs = {}
        if model:
            kwargs["model"] = model
        if base_url:
            kwargs["base_url"] = base_url

        provider = create_provider(name, api_key, **kwargs)
        self._providers[name] = provider

        # 创建对应的 Client
        config = LLMConfig(
            api_key=api_key,
            model=model or "deepseek-chat",
            base_url=base_url or "https://api.deepseek.com/v1",
        )
        self._clients[name] = LLMClient(config)

        if set_default or len(self._providers) == 1:
            self._default_name = name

        logger.info(f"已注册 LLM Provider: {name} (模型: {model or 'default'})")
        return provider

    def get_provider(self, name: str | None = None) -> LLMProvider | None:
        """获取指定 Provider。"""
        name = name or self._default_name
        return self._providers.get(name)

    def get_client(self, name: str | None = None) -> LLMClient | None:
        """获取指定 Client。"""
        name = name or self._default_name
        return self._clients.get(name)

    @property
    def default_client(self) -> LLMClient | None:
        """获取默认 Client。"""
        return self._clients.get(self._default_name)

    @property
    def default_provider(self) -> LLMProvider | None:
        """获取默认 Provider。"""
        return self._providers.get(self._default_name)

    def list_providers(self) -> list[str]:
        """列出所有已注册的 Provider 名称。"""
        return list(self._providers.keys())

    def remove_provider(self, name: str) -> None:
        """移除 Provider。"""
        self._providers.pop(name, None)
        self._clients.pop(name, None)
        if self._default_name == name and self._providers:
            self._default_name = next(iter(self._providers))


__all__ = ["LLMManager"]

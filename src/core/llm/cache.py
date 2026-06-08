"""LLM Cache — 分析/验证结果缓存，避免重复调用。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from loguru import logger


class LLMCache:
    """LLM 结果缓存 — 基于文件系统的简单 KV 缓存。

    Usage:
        cache = LLMCache("data_snapshots/llm_cache")
        cache.set("600519.SH_analysis", analysis_result)
        result = cache.get("600519.SH_analysis")
    """

    def __init__(self, cache_dir: str | Path = "data_snapshots/llm_cache"):
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._enabled: bool = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def get(self, key: str) -> dict[str, Any] | None:
        """获取缓存。"""
        if not self._enabled:
            return None

        filepath = self._key_to_path(key)
        if not filepath.exists():
            return None

        try:
            return json.loads(filepath.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"缓存读取失败 [{key}]: {e}")
            return None

    def set(self, key: str, value: dict[str, Any]) -> None:
        """写入缓存。"""
        if not self._enabled:
            return

        filepath = self._key_to_path(key)
        try:
            filepath.write_text(
                json.dumps(value, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"缓存写入失败 [{key}]: {e}")

    def exists(self, key: str) -> bool:
        """检查缓存是否存在。"""
        return self._key_to_path(key).exists()

    def invalidate(self, key: str) -> None:
        """清除指定缓存。"""
        filepath = self._key_to_path(key)
        if filepath.exists():
            filepath.unlink()

    def clear(self) -> None:
        """清除所有缓存。"""
        for f in self._dir.glob("*.json"):
            f.unlink()
        logger.info(f"已清除 LLM 缓存 ({self._dir})")

    # ── Internal ──────────────────────────────────────────

    def _key_to_path(self, key: str) -> Path:
        """将 key 转为安全文件名。"""
        safe = key.replace("/", "_").replace("\\", "_").replace(":", "_")
        return self._dir / f"{safe}.json"


__all__ = ["LLMCache"]

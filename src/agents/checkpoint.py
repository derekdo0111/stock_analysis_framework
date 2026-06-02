"""
Checkpoint — Agent 工作流检查点/断点续传。

支持:
- 保存 SharedContext 到磁盘
- 从上次检查点恢复
- 防止重复计算（幂等性）
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from src.agents.context import SharedContext


class Checkpoint:
    """Agent 工作流检查点管理。

    Usage:
        cp = Checkpoint("data_snapshots/checkpoints")
        cp.save("600519.SH", context)
        restored = cp.load("600519.SH")
    """

    def __init__(self, checkpoint_dir: str | Path = "data_snapshots/checkpoints"):
        self._dir = Path(checkpoint_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, ts_code: str, context: SharedContext) -> Path:
        """保存检查点。

        Returns:
            检查点文件路径
        """
        filepath = self._code_to_path(ts_code)

        data = {
            "ts_code": ts_code,
            "saved_at": datetime.now().isoformat(),
            "immutable": context.immutable,
            "enriched": context.enriched,
            "opinions": {k: str(v) for k, v in context.opinions.items()},
        }

        filepath.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info(f"检查点已保存: {ts_code} → {filepath}")
        return filepath

    def load(self, ts_code: str) -> SharedContext | None:
        """加载检查点。"""
        filepath = self._code_to_path(ts_code)
        if not filepath.exists():
            return None

        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"检查点加载失败 [{ts_code}]: {e}")
            return None

        ctx = SharedContext(ts_code=ts_code)
        for k, v in data.get("immutable", {}).items():
            ctx.set_immutable(k, v)
        for k, v in data.get("enriched", {}).items():
            ctx.add_enriched(k, v)
        for k, v in data.get("opinions", {}).items():
            ctx.set_opinion(k, v)

        logger.info(f"检查点已恢复: {ts_code}")
        return ctx

    def exists(self, ts_code: str) -> bool:
        """检查是否存在检查点。"""
        return self._code_to_path(ts_code).exists()

    def delete(self, ts_code: str) -> None:
        """删除检查点。"""
        filepath = self._code_to_path(ts_code)
        if filepath.exists():
            filepath.unlink()
            logger.info(f"检查点已删除: {ts_code}")

    def list_checkpoints(self) -> list[str]:
        """列出所有已保存的检查点。"""
        codes = []
        for f in self._dir.glob("*.json"):
            codes.append(f.stem)
        return sorted(codes)

    # ── Internal ──────────────────────────────────────────

    def _code_to_path(self, ts_code: str) -> Path:
        safe = ts_code.replace("/", "_").replace("\\", "_")
        return self._dir / f"{safe}.json"


__all__ = ["Checkpoint"]

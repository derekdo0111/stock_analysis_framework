"""
数据存储层 — JSON(可读调试) + Parquet(高性能查询) 双格式。

设计:
- JSON: 人类可读，用于调试和手动检查
- Parquet: 列式存储，用于批量计算和回测
- 统一接口: save(DataFrame, name) / load(name) → DataFrame
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger


class LocalStorage:
    """本地文件存储 — JSON + Parquet 双格式。

    Usage:
        store = LocalStorage("data_snapshots")
        store.save(df, "600519_daily")
        df = store.load("600519_daily")
    """

    def __init__(self, base_dir: str | Path = "data_snapshots"):
        self._base = Path(base_dir)
        self._json_dir = self._base / "json"
        self._parquet_dir = self._base / "parquet"
        self._json_dir.mkdir(parents=True, exist_ok=True)
        self._parquet_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        df: pd.DataFrame,
        name: str,
        *,
        format: str = "both",  # "json" | "parquet" | "both"
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Path]:
        """保存 DataFrame。

        Args:
            df: 要保存的 DataFrame
            name: 数据集名称 (不含扩展名)
            format: 保存格式
            metadata: 可选元数据 (仅 JSON 格式支持)
        """
        saved: dict[str, Path] = {}

        if format in ("json", "both"):
            json_path = self._json_dir / f"{name}.json"
            records = df.to_dict(orient="records")
            payload: dict[str, Any] = {"name": name, "rows": len(df), "data": records}
            if metadata:
                payload["metadata"] = metadata
            json_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            saved["json"] = json_path
            logger.debug(f"Saved JSON: {json_path} ({len(df)} rows)")

        if format in ("parquet", "both"):
            parquet_path = self._parquet_dir / f"{name}.parquet"
            df.to_parquet(parquet_path, index=False)
            saved["parquet"] = parquet_path
            logger.debug(f"Saved Parquet: {parquet_path} ({len(df)} rows)")

        return saved

    def load(self, name: str, *, prefer: str = "parquet") -> pd.DataFrame:
        """加载数据。

        Args:
            name: 数据集名称 (不含扩展名)
            prefer: 优先格式 "parquet" | "json"
        """
        if prefer == "parquet":
            parquet_path = self._parquet_dir / f"{name}.parquet"
            if parquet_path.exists():
                return pd.read_parquet(parquet_path)

        json_path = self._json_dir / f"{name}.json"
        if json_path.exists():
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            return pd.DataFrame(payload["data"])

        parquet_path = self._parquet_dir / f"{name}.parquet"
        if parquet_path.exists():
            return pd.read_parquet(parquet_path)

        raise FileNotFoundError(f"Dataset '{name}' not found in {self._base}")

    def exists(self, name: str) -> bool:
        """检查数据集是否存在（支持前缀检查: '600519.SH' 匹配 '600519.SH_basic' 等）。"""
        # 精确匹配
        if ((self._json_dir / f"{name}.json").exists() or
            (self._parquet_dir / f"{name}.parquet").exists()):
            return True
        # 前缀匹配（用于检查股票快照是否存在）
        json_files = list(self._json_dir.glob(f"{name}_*.json"))
        parquet_files = list(self._parquet_dir.glob(f"{name}_*.parquet"))
        return len(json_files) > 0 or len(parquet_files) > 0

    def get_paths(self, name: str) -> dict[str, str]:
        """获取数据集的 JSON/Parquet 文件路径。支持前缀匹配。"""
        paths: dict[str, str] = {}
        json_files = list(self._json_dir.glob(f"{name}_*.json")) or list(self._json_dir.glob(f"{name}.json"))
        parquet_files = list(self._parquet_dir.glob(f"{name}_*.parquet")) or list(self._parquet_dir.glob(f"{name}.parquet"))
        if json_files:
            paths["json"] = str(json_files[0])
        if parquet_files:
            paths["parquet"] = str(parquet_files[0])
        return paths

    def list_datasets(self) -> list[str]:
        """列出所有数据集名称。"""
        names: set[str] = set()
        for p in self._json_dir.glob("*.json"):
            names.add(p.stem)
        for p in self._parquet_dir.glob("*.parquet"):
            names.add(p.stem)
        return sorted(names)

    def delete(self, name: str) -> None:
        for d in (self._json_dir, self._parquet_dir):
            for ext in (".json", ".parquet"):
                f = d / f"{name}{ext}"
                if f.exists():
                    f.unlink()

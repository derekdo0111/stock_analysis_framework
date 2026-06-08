"""策略注册表 — 自动发现 src/strategies/ 下所有策略，管理生命周期。"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.strategies.base import BaseStrategy, StrategyMeta

# 项目根
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def discover_strategies() -> list[type["BaseStrategy"]]:
    """自动发现 src/strategies/ 下所有 BaseStrategy 子类。

    发现规则:
    1. 扫描 src/strategies/ 下所有 .py 和子目录
    2. 导入每个模块，查找 BaseStrategy 子类
    3. 返回所有有效的策略类列表

    Returns:
        已发现的策略类列表
    """
    from src.strategies.base import BaseStrategy

    strategies: list[type[BaseStrategy]] = []
    strategies_dir = Path(__file__).resolve().parent

    # 1) 扫描单文件策略 (strategies/xxx.py)
    for finder, name, ispkg in pkgutil.iter_modules([str(strategies_dir)]):
        if name.startswith("_") or name in ("base", "registry"):
            continue
        try:
            module = importlib.import_module(f"src.strategies.{name}")
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseStrategy)
                    and attr is not BaseStrategy
                ):
                    strategies.append(attr)
        except Exception as e:
            # 静默跳过无法导入的模块（模板/空目录等）
            pass

    return strategies


def get_enabled_strategies() -> list[type["BaseStrategy"]]:
    """返回所有 enabled=True 的策略。"""
    from src.strategies.base import BaseStrategy
    return [s for s in discover_strategies() if getattr(s, "_enabled", True)]


def get_registry() -> list["StrategyMeta"]:
    """返回所有已注册策略的元数据列表，供 Web 层使用。"""
    strats = discover_strategies()
    metas = []
    for strat_cls in strats:
        try:
            inst = strat_cls()
            metas.append(inst.get_meta())
        except Exception:
            pass
    return metas

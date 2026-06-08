"""
策略注册表 — 管理 TurtleStrategy 子模块的注册与调度。

用途:
- 注册 OE/PR/L5/打分等计算模块
- 按策略名称查找并实例化
- 支持策略插件化扩展
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Type


@dataclass
class StrategyModule:
    """策略模块描述符。"""
    name: str
    description: str
    module_path: str           # e.g. "src.calculator.turtle_strategy.oe_calculator"
    class_name: str            # e.g. "OECalculator"
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class StrategyRegistry:
    """策略模块注册表。

    Usage:
        registry = StrategyRegistry()
        registry.register(StrategyModule(
            name="owners_earnings",
            description="OE 双路径计算",
            module_path="src.calculator.turtle_strategy.oe_calculator",
            class_name="OECalculator",
        ))
        calculator = registry.get("owners_earnings", client=tushare_client)
    """

    def __init__(self):
        self._modules: dict[str, StrategyModule] = {}

    def register(self, module: StrategyModule) -> None:
        """注册一个策略模块。"""
        self._modules[module.name] = module

    def unregister(self, name: str) -> None:
        """注销一个策略模块。"""
        self._modules.pop(name, None)

    def get_module(self, name: str) -> StrategyModule | None:
        """获取策略模块描述符。"""
        return self._modules.get(name)

    def list_modules(self, enabled_only: bool = True) -> list[StrategyModule]:
        """列出所有已注册模块。"""
        modules = list(self._modules.values())
        if enabled_only:
            modules = [m for m in modules if m.enabled]
        return modules

    def get_instance(self, name: str, **kwargs) -> Any | None:
        """动态导入并实例化策略模块。

        Args:
            name: 模块名称
            **kwargs: 传递给模块构造函数的参数

        Returns:
            策略模块实例，如果导入失败返回 None
        """
        module = self._modules.get(name)
        if module is None:
            return None

        try:
            import importlib
            mod = importlib.import_module(module.module_path)
            cls = getattr(mod, module.class_name)
            return cls(**kwargs)
        except Exception as e:
            raise ImportError(
                f"Failed to load strategy module '{name}' "
                f"({module.module_path}.{module.class_name}): {e}"
            ) from e

    # ── Built-in turtle strategy modules ───────────────────

    def register_turtle_defaults(self) -> None:
        """注册龟龟策略的所有默认子模块。"""
        defaults = [
            StrategyModule(
                name="owners_earnings",
                description="Owners' Earnings 双路径计算 (现金流+利润表)",
                module_path="src.calculator.turtle_strategy.oe_calculator",
                class_name="OECalculator",
            ),
            StrategyModule(
                name="penetration_return",
                description="穿透回报率计算 (分红+回购/可支配现金)",
                module_path="src.calculator.turtle_strategy.pr_calculator",
                class_name="PRCalculator",
            ),
            StrategyModule(
                name="cash_reconciliation",
                description="OE 质量四级验证 (含金量/稳定性/趋势/BS一致性)",
                module_path="src.calculator.turtle_strategy.cash_recon",
                class_name="CashRecon",
            ),
            StrategyModule(
                name="sotp_adjustment",
                description="SOTP 双口径调整 (母公司/合并口径)",
                module_path="src.calculator.turtle_strategy.sotp_adjust",
                class_name="SOTPAdjuster",
            ),
            StrategyModule(
                name="margin_safety",
                description="安全边际 + 3x3 仓位矩阵 + 价值陷阱排查",
                module_path="src.calculator.turtle_strategy.l5_calculator",
                class_name="L5Calculator",
            ),
            StrategyModule(
                name="scoring",
                description="乘法打分 Final = (L2 + L4 + L5) x L3",
                module_path="src.calculator.turtle_strategy.scoring",
                class_name="TurtleScorer",
            ),
        ]
        for mod in defaults:
            self.register(mod)


# ── Global singleton ────────────────────────────────────────
_default_registry: StrategyRegistry | None = None


def get_registry() -> StrategyRegistry:
    """获取全局策略注册表单例。"""
    global _default_registry
    if _default_registry is None:
        _default_registry = StrategyRegistry()
        _default_registry.register_turtle_defaults()
    return _default_registry

"""策略插件基类 — 所有策略必须继承此抽象类。

目录约定:
- 单个 Python 文件:     src/strategies/my_strategy.py (类名 MyStrategy)
- 复杂策略子目录:       src/strategies/my_strategy/ (含 strategy.py 入口)

每个策略需要实现:
- screen(client) → DataFrame: 筛选，返回标准化结果
- analyze(ts_code) → dict:  个股分析，返回报告摘要
- build_report(ts_code) → str: 生成 HTML 报告路径

自动注册:
- 策略类设置 `auto_register = True` 后，系统首次导入时自动写入数据库 strategies 表。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class StrategyMeta:
    """策略元数据 — 注册表条目。"""
    slug: str
    name: str
    description: str = ""
    schedule_cron: str = ""          # e.g. "30 15 * * 5"
    enabled: bool = True
    auto_register: bool = True
    module_path: str = ""            # 完整的 Python 导入路径


class BaseStrategy(ABC):
    """策略抽象基类。

    子类必须设置类属性:
        slug: str        — 唯一标识，如 "turtle" / "dividend"
        name: str        — 中文名称，如 "龟龟策略"
        description: str — 一句话说明
        schedule: str    — cron 表达式，如 "30 15 * * 5"
    """

    # 子类必须覆盖这些类属性
    slug: str = ""
    name: str = ""
    description: str = ""
    schedule: str = ""

    @abstractmethod
    def screen(self, client) -> "pd.DataFrame":
        """筛选：输入 TushareClient，返回标准化结果 DataFrame。

        返回的 DataFrame 必须包含:
        - ts_code, name: 股票代码和名称
        - score: 策略综合得分
        - pool: 分池标签 (核心池/观察池/备选池)
        以及策略特定的列。
        """
        ...

    @abstractmethod
    def analyze(self, ts_code: str) -> dict:
        """个股分析：输入股票代码，返回分析摘要 dict。

        返回内容:
        - final_score: 最终得分 /100
        - breakdown: 各项分解得分
        - qualitative: 定性分析文字
        - report_path: HTML 报告路径
        """
        ...

    @abstractmethod
    def build_report(self, ts_code: str) -> str:
        """生成完整 HTML 报告，返回文件路径。"""
        ...

    def get_meta(self) -> StrategyMeta:
        """返回策略元数据，供注册表使用。"""
        return StrategyMeta(
            slug=self.slug,
            name=self.name,
            description=self.description,
            schedule_cron=self.schedule,
            auto_register=True,
            module_path=f"{self.__class__.__module__}.{self.__class__.__name__}",
        )

"""
Walk-Forward 滚动窗口管理器。

窗口定义:
- 选股期: T-5 到 T 的 5 年财务数据
- 验证期: T+1 到 T+N 的分红数据
- 滑动: T 从 2015 到 2020，每年一个窗口

示例:
  窗口1: 2011-2015 数据选股 → 2016-2020 分红验证
  窗口2: 2012-2016 数据选股 → 2017-2021 分红验证
  ...
  窗口6: 2016-2020 数据选股 → 2021-2025 分红验证
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BacktestWindow:
    """单次回测窗口。"""
    id: int
    label: str
    data_start_year: int  # 财务数据起始年 (5年前)
    data_end_year: int    # 财务数据结束年 (选股决策点)
    validate_start_year: int  # 分红验证起始年
    validate_end_year: int    # 分红验证结束年
    validation_years: int = 5  # 验证年数

    @property
    def data_period(self) -> str:
        return f"{self.data_start_year}-{self.data_end_year}"

    @property
    def validate_period(self) -> str:
        return f"{self.validate_start_year}-{self.validate_end_year}"


class WindowManager:
    """Walk-Forward 窗口生成器。

    默认: 5年数据选股 + 5年分红验证，6个窗口 (2011→2016 到 2016→2021)
    """

    def __init__(
        self,
        data_years: int = 5,
        validation_years: int = 5,
        start_year: int = 2011,
        end_select_year: int = 2020,
    ):
        self.data_years = data_years
        self.validation_years = validation_years
        self.start_year = start_year
        self.end_select_year = end_select_year

    def generate_windows(self) -> list[BacktestWindow]:
        """生成所有 Walk-Forward 窗口。"""
        windows = []
        idx = 1
        for select_year in range(self.start_year, self.end_select_year + 1):
            w = BacktestWindow(
                id=idx,
                label=f"窗口{idx}",
                data_start_year=select_year - self.data_years + 1,
                data_end_year=select_year,
                validate_start_year=select_year + 1,
                validate_end_year=select_year + self.validation_years,
                validation_years=self.validation_years,
            )
            windows.append(w)
            idx += 1
        return windows

    def get_window(self, idx: int) -> BacktestWindow | None:
        windows = self.generate_windows()
        if 0 <= idx - 1 < len(windows):
            return windows[idx - 1]
        return None


# 常用窗口配置
DEFAULT_WINDOWS = [
    BacktestWindow(id=1, label="2011-2015 → 2016-2020",
                   data_start_year=2011, data_end_year=2015,
                   validate_start_year=2016, validate_end_year=2020),
    BacktestWindow(id=2, label="2012-2016 → 2017-2021",
                   data_start_year=2012, data_end_year=2016,
                   validate_start_year=2017, validate_end_year=2021),
    BacktestWindow(id=3, label="2013-2017 → 2018-2022",
                   data_start_year=2013, data_end_year=2017,
                   validate_start_year=2018, validate_end_year=2022),
    BacktestWindow(id=4, label="2014-2018 → 2019-2023",
                   data_start_year=2014, data_end_year=2018,
                   validate_start_year=2019, validate_end_year=2023),
    BacktestWindow(id=5, label="2015-2019 → 2020-2024",
                   data_start_year=2015, data_end_year=2019,
                   validate_start_year=2020, validate_end_year=2024),
    BacktestWindow(id=6, label="2016-2020 → 2021-2025",
                   data_start_year=2016, data_end_year=2020,
                   validate_start_year=2021, validate_end_year=2025),
]

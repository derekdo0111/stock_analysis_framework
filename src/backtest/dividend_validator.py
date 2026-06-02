"""
分红验证器 — PR 兑现率 vs PR 阈值。

回测核心判断:
1. PR 兑现率 = 实际股息回报 / 预测 PR   (≥0.7 为合格)
2. 实际股息回报 ≥ PR 最低阈值(5%)    (选股逻辑是否有效)
3. 分组对比: Top5 vs Bottom5 的股息差 (打分区分度)

对比基准: 穿透回报率的三级阈值
  ≥12% 优秀 / ≥8% 良好 / ≥5% 及格 / <5% 不及格
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from src.data_pool.bundle import StockDataBundle
from src.backtest.window_manager import BacktestWindow


# PR 阈值 (来自 turtle_constants.yaml)
PR_THRESHOLDS = {
    "excellent": 12.0,   # 优秀
    "good": 8.0,         # 良好
    "pass": 5.0,         # 及格 (最低门槛)
    "fail": 0.0,         # 不及格 L4=0
}
PR_MIN_THRESHOLD = 5.0   # 选股最低门槛


@dataclass
class DividendValidation:
    """单只股票在一个窗口的分红验证结果。"""
    ts_code: str
    name: str = ""

    # 预测值
    predicted_pr_pct: float = 0.0

    # 实际值
    actual_dividend_yield: float = 0.0
    actual_dividends: list[float] = field(default_factory=list)

    # 核心指标
    pr_fulfillment: float = 0.0  # 实际 / 预测，≥0.7 合格
    pr_threshold_met: bool = False  # 实际 ≥ PR最低阈值(5%)

    # 判定
    is_pr_qualified: bool = False  # 兑现率 ≥ 0.7
    is_threshold_valid: bool = False  # 实际 ≥ 5%

    # 元数据
    window_id: int = 0
    final_score: float = 0.0


class DividendValidator:
    """分红验证器 — 对比 PR 门槛而非无风险利率。"""

    def __init__(self, bundle: StockDataBundle):
        self._bundle = bundle

    def validate(
        self,
        ts_code: str,
        name: str,
        predicted_pr_pct: float,
        window: BacktestWindow,
        final_score: float = 0,
    ) -> DividendValidation:
        """验证单只股票在指定窗口的分红。

        Args:
            ts_code: 股票代码
            name: 股票名称
            predicted_pr_pct: 预测穿透回报率 (%)
            window: 回测窗口
            final_score: 最终得分
        """
        result = DividendValidation(
            ts_code=ts_code,
            name=name,
            predicted_pr_pct=predicted_pr_pct,
            window_id=window.id,
            final_score=final_score,
        )

        # 拉取验证期实际分红（按年汇总）+ 年末股价
        yearly_dividends = self._fetch_dividends(ts_code, window)
        result.actual_dividends = list(yearly_dividends.values())

        # 计算年化股息回报（%）= 每股年分红 / 年末股价 × 100
        if yearly_dividends:
            yields_pct = []
            for year, div_per_share in yearly_dividends.items():
                price = self._get_year_end_price(ts_code, year)
                if price and price > 0:
                    yields_pct.append(div_per_share / price * 100)
            if yields_pct:
                result.actual_dividend_yield = round(float(np.mean(yields_pct)), 2)

        # 核心判定
        if result.predicted_pr_pct > 0 and result.actual_dividend_yield > 0:
            result.pr_fulfillment = round(
                result.actual_dividend_yield / result.predicted_pr_pct, 2
            )

        # 判定1: PR 兑现率 ≥ 0.7
        result.is_pr_qualified = result.pr_fulfillment >= 0.7

        # 判定2: 实际股息回报 ≥ PR最低阈值(5%)
        result.pr_threshold_met = result.actual_dividend_yield >= PR_MIN_THRESHOLD

        return result

    def _get_year_end_price(self, ts_code: str, year: int) -> float | None:
        """获取年末收盘价，从 bundle 过滤。"""
        try:
            end_date = f"{year}1231"
            df = self._bundle.daily
            row = df[df["trade_date"].astype(str) == end_date]
            if not row.empty:
                close = row.iloc[0].get("close")
                if close and float(close) > 0:
                    return float(close)
        except Exception:
            pass
        # fallback: 往前找最近交易日
        for day_offset in range(1, 10):
            try:
                day = 31 - day_offset
                if day < 1:
                    break
                alt_date = f"{year}12{day:02d}"
                row = self._bundle.daily[self._bundle.daily["trade_date"].astype(str) == alt_date]
                if not row.empty:
                    close = row.iloc[0].get("close")
                    if close and float(close) > 0:
                        return float(close)
            except Exception:
                continue
        return None

    def _fetch_dividends(self, ts_code: str, window: BacktestWindow) -> dict[int, float]:
        """从 bundle 读取验证期每年分红总额（元/股，按年汇总多次公告）。

        Returns:
            {year: total_cash_div_per_share}  — 每股年分红合计
        """
        try:
            df = self._bundle.dividend
            if df.empty:
                return {}
            yearly: dict[int, float] = {}
            for _, row in df.iterrows():
                end_date = str(row.get("end_date", ""))
                if not end_date or len(end_date) < 4:
                    continue
                year = int(end_date[:4])
                if window.validate_start_year <= year <= window.validate_end_year:
                    # 优先用 cash_div_tax（税前），fallback 到 cash_div
                    cash_div = float(
                        row.get("cash_div_tax") or row.get("cash_div") or 0
                    )
                    proc = str(row.get("div_proc", "")).strip()
                    if cash_div > 0 and proc in ("实施", "股东大会通过"):
                        yearly[year] = yearly.get(year, 0) + cash_div
            return yearly
        except Exception:
            return {}

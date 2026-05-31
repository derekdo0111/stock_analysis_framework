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

from src.data_fetcher.tushare_client import TushareClient
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

    def __init__(self, client: TushareClient):
        self._client = client

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

        # 拉取验证期实际分红
        dividends = self._fetch_dividends(ts_code, window)
        result.actual_dividends = dividends

        # 计算实际年化股息回报
        if dividends:
            positives = [d for d in dividends if d > 0]
            if positives:
                result.actual_dividend_yield = round(float(np.mean(positives)), 2)

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

    def _fetch_dividends(self, ts_code: str, window: BacktestWindow) -> list[float]:
        """拉取验证期的每股派息(元)。"""
        try:
            df = self._client.dividend(ts_code=ts_code)
            if df.empty:
                return []
            dividends = []
            for _, row in df.iterrows():
                end_date = str(row.get("end_date", ""))
                if not end_date or len(end_date) < 4:
                    continue
                year = int(end_date[:4])
                if window.validate_start_year <= year <= window.validate_end_year:
                    cash_div = float(row.get("cash_div") or 0)
                    if cash_div > 0 and str(row.get("div_proc", "")).strip() == "实施":
                        dividends.append(cash_div)
            return dividends
        except Exception:
            return []

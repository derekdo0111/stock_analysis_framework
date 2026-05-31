"""
管线运行器 — 每窗口跑完整选股→打分管线。

对每个窗口:
1. 从全市场选股池中筛选 (HardGate + L2 + 分类)
2. 对通过股票计算完整打分 (OE → PR → L5 → Final)
3. 存入验证队列
"""

from __future__ import annotations

from dataclasses import dataclass, field

from loguru import logger

from src.data_fetcher.tushare_client import TushareClient
from src.screener.hard_gate import HardGateChecker
from src.screener.l2_screener import L2Screener
from src.screener.classifier import CompanyClassifier
from src.calculator.turtle_strategy.scoring import TurtleScorer, FinalScore
from src.backtest.window_manager import BacktestWindow


@dataclass
class WindowResult:
    """单个窗口的完整结果。"""
    window: BacktestWindow
    stocks: list[FinalScore] = field(default_factory=list)
    passed: int = 0
    failed_hard_gate: int = 0
    failed_l2: int = 0
    failed_classify: int = 0


class PipelineRunner:
    """回测管线运行器。

    对每个窗口: HardGate → L2 → 分类 → 打分
    """

    def __init__(self, client: TushareClient):
        self._client = client
        self._hard_gate = HardGateChecker(client)
        self._l2 = L2Screener(client)
        self._classifier = CompanyClassifier(client)
        self._scorer = TurtleScorer(client)

    def run_window(
        self,
        window: BacktestWindow,
        ts_codes: list[str] | None = None,
    ) -> WindowResult:
        """运行单个窗口的完整管线。

        Args:
            window: 回测窗口
            ts_codes: 待选股票列表，None=自动获取全市场
        """
        result = WindowResult(window=window)

        if ts_codes is None:
            ts_codes = self._get_universe()

        logger.info(f"{window.label}: 全市场 {len(ts_codes)} 只股票")

        for code in ts_codes:
            # HardGate
            hg = self._hard_gate.check(code)
            if not hg.passed:
                result.failed_hard_gate += 1
                continue

            # L2
            l2 = self._l2.score(code)
            if l2.eliminated:
                result.failed_l2 += 1
                continue

            # 分类
            cls = self._classifier.classify(code)
            if not cls.eligible:
                result.failed_classify += 1
                continue

            # 打分
            try:
                final = self._scorer.score(code)
                if final.is_valid:
                    result.stocks.append(final)
                    result.passed += 1
            except Exception as e:
                logger.warning(f"打分失败 {code}: {e}")

        logger.info(
            f"{window.label}: 通过 {result.passed}, "
            f"否决 {result.failed_hard_gate}, "
            f"L2淘汰 {result.failed_l2}, "
            f"分类排除 {result.failed_classify}"
        )
        return result

    def _get_universe(self) -> list[str]:
        """获取全市场股票池。"""
        try:
            df = self._client.stock_basic()
            return df["ts_code"].tolist()[:100]  # 限制100只用于回测
        except Exception:
            # 降级: 返回常见股票
            return [
                "600519.SH", "000858.SZ", "000568.SZ",  # 茅台/五粮液/老窖
                "000333.SZ", "002415.SZ",                # 美的/海康
                "600276.SH", "300760.SZ",                # 恒瑞/迈瑞
                "000002.SZ", "601318.SH",                # 万科/平安
            ]

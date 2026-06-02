"""
回测入口脚本 — Walk-Forward 分红验证。

用法:
    python examples/run_backtest.py              # 全部6窗口，预设9只股票
    python examples/run_backtest.py --window 6   # 仅窗口6 (2016-2020 → 2021-2025)
    python examples/run_backtest.py --stocks 50  # 全市场前50只
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 确保 src 在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from loguru import logger

from src.data_fetcher.tushare_client import TushareClient
from src.backtest.window_manager import WindowManager, DEFAULT_WINDOWS
from src.backtest.pipeline_runner import PipelineRunner
from src.backtest.dividend_validator import DividendValidator
from src.backtest.statistics import BacktestStatistics
from src.backtest.report import BacktestReportGenerator


PRESET_STOCKS = [
    "600519.SH",  # 茅台
    "000858.SZ",  # 五粮液
    "000568.SZ",  # 泸州老窖
    "000333.SZ",  # 美的集团
    "002415.SZ",  # 海康威视
    "600276.SH",  # 恒瑞医药
    "600900.SH",  # 长江电力
    "000002.SZ",  # 万科A
    "601318.SH",  # 中国平安
]


def main():
    parser = argparse.ArgumentParser(description="龟龟策略 Walk-Forward 回测")
    parser.add_argument("--window", type=int, default=0,
                        help="只跑指定窗口 (1-6)，0=全部")
    parser.add_argument("--stocks", type=int, default=0,
                        help="从全市场取前N只，0=用预设列表")
    parser.add_argument("--output", type=str, default="backtest_report.html",
                        help="报告输出路径")
    args = parser.parse_args()

    logger.info("初始化 Tushare 客户端...")
    client = TushareClient()

    # 选窗口
    wm = WindowManager()
    all_windows = wm.generate_windows()
    if args.window > 0:
        windows = [w for w in all_windows if w.id == args.window]
        if not windows:
            logger.error(f"窗口 {args.window} 不存在")
            return
    else:
        windows = all_windows
    logger.info(f"待跑窗口: {[w.label for w in windows]}")

    # 选股票
    if args.stocks > 0:
        df = client.stock_basic()
        ts_codes = df["ts_code"].tolist()[:args.stocks]
    else:
        ts_codes = PRESET_STOCKS
    logger.info(f"股票池: {len(ts_codes)} 只")

    # 管线 + 验证
    runner = PipelineRunner(client)
    validator = DividendValidator(client)
    stats = BacktestStatistics()

    all_window_stats = []
    all_validations = []

    for window in windows:
        logger.info(f"\n{'='*60}\n  {window.label}\n{'='*60}")

        # Step 1: 跑管线 (HardGate → L2 → 分类 → 打分)
        result = runner.run_window(window, ts_codes)
        logger.info(
            f"  通过={result.passed} 否决={result.failed_hard_gate} "
            f"L2淘汰={result.failed_l2} 分类排除={result.failed_classify}"
        )

        if not result.stocks:
            logger.warning(f"  {window.label}: 无股票通过管线")
            continue

        # Step 2: 分红验证
        window_validations = []
        for final in result.stocks:
            try:
                v = validator.validate(
                    ts_code=final.ts_code,
                    name=final.name,
                    predicted_pr_pct=final.pr_pct,
                    window=window,
                    final_score=final.final_score,
                )
                window_validations.append(v)
                logger.info(
                    f"  {final.name}({final.ts_code}): "
                    f"PR预测={final.pr_pct:.1f}% "
                    f"实际股息={v.actual_dividend_yield:.1f}% "
                    f"兑现率={v.pr_fulfillment:.2f} "
                    f"{'✅' if v.is_pr_qualified else '❌'}"
                )
            except Exception as e:
                logger.warning(f"  验证失败 {final.ts_code}: {e}")

        all_validations.extend(window_validations)

        # Step 3: 统计
        ws = stats.analyze_window(window_validations, window.id, window.label)
        all_window_stats.append(ws)
        logger.info(
            f"  窗口统计: 股票={ws.total_stocks} "
            f"平均兑现率={ws.avg_fulfillment:.2f} "
            f"兑现合格率={ws.pr_fulfill_qualified_pct:.0f}% "
            f"阈值达标率={ws.threshold_met_pct:.0f}% "
            f"Top5-Bottom5差={ws.spread:.1f}%"
        )

    # Step 4: 跨窗口汇总
    if all_window_stats:
        cross = stats.analyze_cross_window(all_window_stats)
        logger.info(
            f"\n{'='*60}\n  跨窗口汇总\n{'='*60}\n"
            f"  窗口数={cross.total_windows} "
            f"平均兑现率={cross.avg_fulfillment:.2f} "
            f"平均阈值达标率={cross.avg_threshold_met_pct:.0f}% "
            f"平均Spread={cross.avg_spread:.1f}% "
            f"区分度={'✅' if cross.has_discrimination else '❌'}"
        )

        # Step 5: 生成报告
        gen = BacktestReportGenerator()
        output_path = Path(args.output)
        gen.save(all_window_stats, cross, output_path)
        logger.info(f"\n报告已保存: {output_path.resolve()}")
    else:
        logger.error("无有效窗口数据，无法生成报告")


if __name__ == "__main__":
    main()

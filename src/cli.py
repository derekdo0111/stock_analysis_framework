"""
CLI 入口 — stock-analyze 命令。

v0.27: 统一三阶段 LLM 管线。默认运行完整管线:
  Phase 1→2→3→3.5→4→5a→5b→6

Usage:
    stock-analyze 600519.SH                # 完整管线 (含三阶段 LLM)
    stock-analyze 600519.SH --no-llm       # 仅 Python 计算 (跳过 LLM)
    stock-analyze 600519.SH --html         # 输出 HTML 报告
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

import pandas as pd  # noqa: F401

# Load .env before anything else
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _a(s: str) -> str:
    """Replace emoji with ASCII-safe equivalents for Windows GBK console."""
    return s.replace("\U0001f7e2", "[OK]").replace("\U0001f7e1", "[?]").replace("\U0001f534", "[!!]")


def _out_dir(ts_code: str, name: str = "") -> str:
    """返回默认输出子目录路径，自动创建。

    格式: output/{代码}_{名称}/  如 output/600519_SH_贵州茅台/
    """
    code_part = ts_code.replace(".", "_")
    if name:
        folder = f"{code_part}_{name}"
    else:
        folder = code_part
    d = os.path.join("output", folder)
    os.makedirs(d, exist_ok=True)
    return d


def main():
    parser = argparse.ArgumentParser(
        description="龟龟投资策略 v0.27 — A股选股到报告生成全管线 (三阶段LLM)",
    )
    parser.add_argument("ts_code", nargs="?", help="股票代码 (如 600519.SH)")
    parser.add_argument("--no-llm", action="store_true", help="跳过所有 LLM 阶段 (仅 Python 计算)")
    parser.add_argument("--html", action="store_true", help="输出 HTML 完整报告")
    parser.add_argument("--output", "-o", default="", help="报告输出路径")
    parser.add_argument("--token", help="Tushare Token (可选，默认读 .env)")

    args = parser.parse_args()

    if not args.ts_code:
        parser.print_help()
        return

    if args.token:
        os.environ["TUSHARE_TOKEN"] = args.token

    from src.data_fetcher.tushare_client import TushareClient
    from src.data_fetcher.orchestrator import DataPoolOrchestrator
    from src.calculator.turtle_strategy.scoring import TurtleScorer

    print(f"[Turtle] v0.27 -- Analyzing {args.ts_code}")
    print("=" * 60)

    # ══════════════════════════════════════════════════════════
    # Phase 1: 数据快照（唯一调用 Tushare 的入口）
    # ══════════════════════════════════════════════════════════
    print("[Phase 1] 数据快照...")
    try:
        client = TushareClient(token=args.token or None)
        orch = DataPoolOrchestrator(client)
        snap_result = orch.snapshot_stock(args.ts_code)
        if not snap_result.success:
            print(f"[ERROR] 数据快照失败: {snap_result.errors}")
            sys.exit(1)
        print(f"  已拉取 {snap_result.datasets_stored} 个数据集")
        bundle = orch.get_bundle(args.ts_code)
        if bundle is None:
            print(f"[ERROR] 无法加载缓存数据")
            sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 数据拉取失败: {e}")
        sys.exit(1)

    # ══════════════════════════════════════════════════════════
    # Phase 2: 量化打分（纯读缓存）
    # ══════════════════════════════════════════════════════════
    print("[Phase 2] 量化打分...")
    try:
        scorer = TurtleScorer(bundle)
        result = scorer.score(args.ts_code)
    except Exception as e:
        print(f"[ERROR] 打分失败: {e}")
        sys.exit(1)

    print(f"  L2(门控)={result.l2_score}  L3={result.l3_score}/30 ({result.l3_level})  L4={result.l4_score}/45  L5={result.l5_score}/25")
    print(f"  Final={result.final_score}/100  Pool={result.pool}")
    print(f"  PR={result.pr_pct:.2f}%  OE={_a(result.oe_quality)}  仓位={result.position_pct}%")
    if result.pr_distribution_source:
        src_label = "承诺" if "tier1" in result.pr_distribution_source else "外推"
        print(f"  分配比率={result.pr_distribution_ratio:.1f}%({src_label})  可支配现金={result.pr_disposable_cash:.0f}万  回购注销={result.pr_buyback_cancellation:.0f}万")

    # 打印详细分解
    print(f"\n  --- Breakdown ---")
    print(f"  HardGate: {'PASS' if result.hard_gate_passed else 'VETO'}")
    print(f"  L2(门控): {result.l2_details}")
    print(f"  Classify: {result.classify_type}")
    print(f"  L3: {result.l3_score}/30 ({result.l3_level})  dim-score={result.l3_total_dim}/24")
    print(f"  L4 PR: {result.pr_pct:.2f}%  start={result.pr_starting_score}  penalty={result.pr_quality_penalty}  OE={_a(result.oe_quality)}")
    print(f"  PR: DC={result.pr_disposable_cash:.0f}万  ratio={result.pr_distribution_ratio:.1f}%({result.pr_distribution_source})  buyback={result.pr_buyback_cancellation:.0f}万")
    print(f"  L5 估值安全边际率: {result.l5_safety_margin_pct:.1f}%  估值得分: {result.l5_valuation_score}/15  缓冲: {result.l5_downside_score}/5")
    print(f"  L5 仓位: {result.position_pct}%")

    # ══════════════════════════════════════════════════════════
    # Phase 3: 财报深度分析 (7模块纯Python)
    # ══════════════════════════════════════════════════════════
    financial_insights = None
    print("\n[Phase 3] 财报深度分析 (7模块)...")
    from src.calculator.financial_deep_analysis import FinancialDeepAnalyzer
    try:
        fa = FinancialDeepAnalyzer(bundle)
        financial_insights = fa.analyze()
        print(f"  模块1 收入利润: {financial_insights.revenue_trend_str[:80]}...")
        print(f"  模块2 利润率:   {financial_insights.margin_trend_str[:80]}...")
        print(f"  模块3 ROE杜邦:  {financial_insights.roe_trend_str[:80]}...")
        print(f"  模块4 现金流:   {financial_insights.cash_quality_str[:80]}...")
        print(f"  模块5 资产负债: {financial_insights.balance_health_str[:80]}...")
        print(f"  模块6 分红政策: {financial_insights.dividend_policy_str[:80]}...")
        print(f"  模块7 营运效率: {financial_insights.efficiency_str[:80]}...")
        orch.cache_financial_insights(args.ts_code, financial_insights)
    except Exception as e:
        print(f"  [WARN] 财报深度分析失败: {e}")

    # ══════════════════════════════════════════════════════════
    # LLM Phases (3.5 + 5a + 5b)
    # ══════════════════════════════════════════════════════════
    business_knowledge = None
    analysis_result = None
    cv_result = None

    if args.no_llm:
        print("\n[LLM] --no-llm 模式，跳过所有 LLM 阶段")
    else:
        from src.llm.client import LLMConfig

        if not LLMConfig.is_configured():
            print("\n[LLM] 未配置 LLM API Key，跳过 LLM 阶段")
        else:
            print(f"\n[LLM] Provider: {LLMConfig.provider() or 'deepseek'} | "
                  f"Retrieval: {LLMConfig.retrieval_model()} | "
                  f"Analysis: {LLMConfig.analysis_model()} | "
                  f"Validation: {LLMConfig.validation_model()}")

            # ── Phase 3.5: 商业知识检索 LLM ──
            print("\n[Phase 3.5] LLM 商业知识检索 (web_search)...")
            from src.llm.business_retrieval_agent import BusinessRetrievalAgent

            # 提取行业和基本估值信息
            industry = ""
            if hasattr(bundle, 'industry') and bundle.industry:
                industry = str(bundle.industry)
            market_cap = 0.0
            db = bundle.daily_basic
            if not db.empty:
                latest_mv = db.sort_values("trade_date", ascending=False).iloc[0].get("total_mv")
                if latest_mv and not (isinstance(latest_mv, float) and pd.isna(latest_mv)):
                    market_cap = float(latest_mv) / 1e4  # 万元→亿元

            try:
                br_agent = BusinessRetrievalAgent()
                business_knowledge = br_agent.retrieve(
                    ts_code=args.ts_code,
                    company_name=bundle.name,
                    industry=industry,
                    market_cap=market_cap,
                )
                if business_knowledge.success:
                    confs = [
                        business_knowledge.business_model_confidence,
                        business_knowledge.management_confidence,
                        business_knowledge.industry_position_confidence,
                        business_knowledge.risk_regulation_confidence,
                        business_knowledge.dividend_buyback_confidence,
                    ]
                    high = sum(1 for c in confs if c == "high")
                    print(f"  商业检索完成 (source={business_knowledge.source})")
                    print(f"  置信度: high={high}/5, 来源URL数={len(business_knowledge.source_urls)}")
                else:
                    print(f"  [INFO] 商业检索跳过: {business_knowledge.error or 'API 不可用'}")
            except Exception as e:
                print(f"  [WARN] 商业检索失败: {e}")

            # ── Phase 4: 组装完整 brief.md ──
            print("\n[Phase 4] 组装完整 brief.md 数据底稿...")
            from src.reporter.brief_md_builder import BriefMDBuilder
            builder = BriefMDBuilder(bundle, result, financial_insights, business_knowledge)
            brief_md = builder.build()

            output_dir = args.output.rsplit("/", 1)[0] if args.output else _out_dir(args.ts_code, bundle.name)
            brief_md_path = os.path.join(output_dir, f"brief_{args.ts_code.replace('.', '_')}.md")
            os.makedirs(os.path.dirname(brief_md_path), exist_ok=True)
            with open(brief_md_path, "w", encoding="utf-8") as f:
                f.write(brief_md)
            print(f"  brief.md 已保存: {brief_md_path}")

            # ── Phase 5a: 分析 LLM Agent ──
            print("\n[Phase 5a] 分析 LLM Agent (基于完整 brief.md)...")
            from src.llm.analysis_agent import AnalysisAgent
            try:
                aa = AnalysisAgent()
                analysis_result = aa.analyze(brief_md, bundle.name, args.ts_code)
                if analysis_result.success:
                    tags = "[LLM]"
                    print(f"  分析Agent: {analysis_result.qualitative_total}/45  "
                          f"({analysis_result.business_model}) {tags}")
                    if analysis_result.module_details:
                        for md in analysis_result.module_details[:5]:  # 只显示前5个
                            name = md.get("module", "?")
                            s = md.get("score", 0)
                            conf = md.get("confidence", "?")
                            bar = "#" * int(s) + "-" * (5 - int(s))
                            print(f"    {bar} {name}: {s}/5 ({conf})")
                        if len(analysis_result.module_details) > 5:
                            print(f"    ... 共 {len(analysis_result.module_details)} 个模块")
                    if analysis_result.red_flags:
                        for rf in analysis_result.red_flags:
                            print(f"    [!!] {rf}")
                else:
                    print(f"  [WARN] 分析Agent失败: {analysis_result.error}")
            except Exception as e:
                print(f"  [WARN] 分析Agent异常: {e}")

            # ── Phase 5b: 交叉验证 LLM Agent ──
            print("\n[Phase 5b] 交叉验证 LLM Agent (事实核查模式)...")
            from src.llm.cross_validation_agent import CrossValidationAgent

            analysis_text = ""
            if analysis_result and analysis_result.success:
                analysis_text = (
                    analysis_result.full_report
                    or f"分析报告: 定性总分={analysis_result.qualitative_total}/45, "
                       f"商业模式={analysis_result.business_model}, "
                       f"红旗={len(analysis_result.red_flags)}"
                )

            try:
                cv_agent = CrossValidationAgent()
                cv_result = cv_agent.validate(analysis_text, brief_md, bundle.name, args.ts_code)
                if cv_result.success:
                    print(f"  核查项: {cv_result.total_checked}")
                    print(f"  [OK]可支撑: {cv_result.supported_count} | "
                          f"[?]过度解读: {cv_result.overstatement_count} | "
                          f"[X]矛盾: {cv_result.conflict_count} | "
                          f"[??]缺证据: {cv_result.evidence_lack_count}")
                    if cv_result.used_fallback:
                        print(f"  [INFO] 降级规则引擎")
                    if cv_result.red_flags:
                        for rf in cv_result.red_flags:
                            print(f"    [!!] {_a(rf)}")
                    if cv_result.overall_verdict:
                        print(f"  总体结论: {_a(cv_result.overall_verdict[:120])}...")
                else:
                    print(f"  [WARN] 交叉验证失败: {cv_result.error}")
            except Exception as e:
                print(f"  [WARN] 交叉验证异常: {e}")

    # ══════════════════════════════════════════════════════════
    # Phase 6: HTML 报告
    # ══════════════════════════════════════════════════════════
    if args.html:
        print("\n[Phase 6] 生成 HTML 完整报告...")
        from src.reporter.report_generator import ReportGenerator
        gen = ReportGenerator()
        output = args.output or os.path.join(_out_dir(args.ts_code, bundle.name), f"report_{args.ts_code.replace('.', '_')}.html")
        gen.save(result, output, None)  # Use old signature for backward compat
        print(f"  完整报告已保存: {output}")

        # 如果有 LLM 结果，生成含交叉验证的增强报告
        if cv_result and cv_result.success:
            cv_output = output.replace(".html", "_cv.html")
            try:
                gen.save_cross_validated(result, cv_result, financial_insights, cv_output, None)
                print(f"  交叉验证报告已保存: {cv_output}")
            except Exception as e:
                print(f"  [WARN] 交叉验证报告生成失败: {e}")

    elif not args.no_llm and business_knowledge:
        # 无 --html 时也保存 brief.md（已在 Phase 4 保存）
        pass

    print("\n[DONE] Analysis complete.")


if __name__ == "__main__":
    main()

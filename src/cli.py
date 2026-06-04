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
        description="龟龟投资策略 v0.32 — A股选股到报告生成全管线 (三阶段LLM)",
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

    print(f"[Turtle] v0.32 -- Analyzing {args.ts_code}")
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
    claim_verification: dict = {"result": None}  # v0.30

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
            analysis_text = ""
            try:
                aa = AnalysisAgent()
                analysis_result = aa.analyze(brief_md, bundle.name, args.ts_code)
                if analysis_result.success:
                    tags = "[LLM]"
                    print(f"  分析Agent: {analysis_result.qualitative_total}/45  "
                          f"({analysis_result.business_model}) {tags}")
                    analysis_text = analysis_result.full_report or f"分析报告: 定性总分={analysis_result.qualitative_total}/45"
                    if analysis_result.module_details:
                        for md in analysis_result.module_details[:5]:
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

            # ── v0.30 ──
            # Phase 5a.5: 声明提取（分析Agent自拆原子声明）
            # Phase 5b: 逐条 CV 核查
            # Phase 5b.5: 分析Agent回炉修正
            # Phase 5c: 根因反思
            # ──────────────────────────────────────────────────

            cv_result = None  # 保留旧接口兼容性

            from src.llm.claim_types import ClaimVerificationResult
            claim_result = ClaimVerificationResult(
                ts_code=args.ts_code,
                name=bundle.name,
            )

            if analysis_text:
                # ── Phase 5a.5: 声明提取 ──
                print("\n[Phase 5a.5] 声明提取 (从分析报告拆解原子声明)...")
                claims = aa.extract_claims(analysis_text, brief_md, bundle.name, args.ts_code)
                if claims:
                    print(f"  提取 {len(claims)} 条原子声明:")
                    type_counts: dict[str, int] = {}
                    for c in claims:
                        t = c.claim_type
                        type_counts[t] = type_counts.get(t, 0) + 1
                    for t, cnt in sorted(type_counts.items()):
                        type_names = {
                            "pipeline_calculation": "管线计算",
                            "data_citation": "数据引用",
                            "trend_judgment": "趋势判断",
                            "business_assertion": "商业断言",
                            "qualitative_score": "定性打分",
                        }
                        print(f"    {type_names.get(t, t)}: {cnt} 条")
                else:
                    print(f"  [WARN] 声明提取为空或失败")

                if claims:
                    # ── Phase 5b: 逐条 CV 核查 ──
                    print(f"\n[Phase 5b] 交叉验证 (逐条核查 {len(claims)} 条声明)...")
                    from src.llm.cross_validation_agent import CrossValidationAgent
                    try:
                        cv_agent = CrossValidationAgent()
                        verified_claims = cv_agent.verify_claims_batch(
                            claims, brief_md, bundle.name, args.ts_code
                        )
                        claim_result.verified_claims = verified_claims
                        claim_result.refresh_stats()
                        print(f"  核查完成: "
                              f"  [OK]={claim_result.supported_count}"
                              f"  [?]={claim_result.overstatement_count}"
                              f"  [X]={claim_result.conflict_count}"
                              f"  [??]={claim_result.evidence_lack_count}")
                        # 列出问题项
                        issues_found = [
                            vc for vc in verified_claims if "源数据可支撑" not in str(vc.judgment)
                        ]
                        if issues_found:
                            print(f"  问题项 ({len(issues_found)} 条):")
                            for vc in issues_found[:5]:
                                short = vc.claim_text[:60] if vc.claim_text else "?"
                                tag = str(vc.judgment)[:10]
                                print(f"    [{tag}] {short}...")
                            if len(issues_found) > 5:
                                print(f"    ... 共 {len(issues_found)} 条")
                        else:
                            print(f"  [OK] 所有声明核查通过!")
                    except Exception as e:
                        print(f"  [WARN] 逐条核查异常: {e}")
                        import traceback
                        traceback.print_exc()

                    # ── Phase 5b.5: 回炉修正 (仅有问题项时触发) ──
                    if claim_result.verified_claims:
                        conflict = claim_result.conflict_count
                        overstate = claim_result.overstatement_count
                        lack = claim_result.evidence_lack_count
                        if conflict + overstate + lack == 0:
                            print(f"\n[Phase 5b.5] 回炉修正: 全部通过，跳过")
                        else:
                            print(f"\n[Phase 5b.5] 回炉修正 (分析Agent审阅CV结果)...")
                            try:
                                revised_claims, revised_report = aa.revise_with_cv_feedback(
                                    claims=claims,
                                    verified_claims=claim_result.verified_claims,
                                    analysis_text=analysis_text,
                                    brief_md=brief_md,
                                    company_name=bundle.name,
                                    ts_code=args.ts_code,
                                )
                                claim_result.revised_claims = revised_claims
                                claim_result.revised_report = revised_report
                                claim_result.refresh_stats()
                                print(f"  修正完成: accept={claim_result.accepted_count} "
                                      f"dispute={claim_result.disputed_count} "
                                      f"clarify={claim_result.clarified_count}")
                                # 更新 analysis_text 为修正后的版本
                                if revised_report:
                                    analysis_text = revised_report
                            except Exception as e:
                                print(f"  [WARN] 回炉修正异常: {e}")

                    # ── 为旧 cv_result 兼容层构造一个模拟结果 ──
                    from src.llm.cross_validation_agent import CrossValidationResult, Discrepancy
                    cv_result = CrossValidationResult(
                        ts_code=args.ts_code,
                        name=bundle.name,
                        success=True,
                    )
                    discrepancies = []
                    for vc in claim_result.verified_claims:
                        discrepancies.append(Discrepancy(
                            dimension=vc.dimension or "",
                            quantitative_score=vc.claim_text or "",
                            evidence=vc.evidence or "",
                            judgment=vc.judgment or "?缺乏证据",
                            suggestion=vc.suggestion or "",
                            severity=vc.severity or "INFO",
                        ))
                    cv_result.discrepancies = discrepancies
                    cv_result.total_checked = claim_result.total_claims
                    cv_result.supported_count = claim_result.supported_count
                    cv_result.overstatement_count = claim_result.overstatement_count
                    cv_result.conflict_count = claim_result.conflict_count
                    cv_result.evidence_lack_count = claim_result.evidence_lack_count
                    cv_result.overall_verdict = f"逐条核查 {claim_result.total_claims} 项" + \
                        (f"，✓={claim_result.supported_count}" if claim_result.supported_count else "") + \
                        (f"，问题项={claim_result.overstatement_count + claim_result.conflict_count + claim_result.evidence_lack_count}" if (claim_result.overstatement_count + claim_result.conflict_count + claim_result.evidence_lack_count) else f"，全部通过")

                    claim_result.success = True

            claim_verification["result"] = claim_result

    # ══════════════════════════════════════════════════════════
    # Phase 5c: 根因反思 (v0.29 → v0.30: 使用逐条核查结果)
    # ══════════════════════════════════════════════════════════
    root_cause_result = None
    if not args.no_llm and analysis_result and analysis_result.success:
        # v0.30: 优先使用逐条核查结果
        clr = claim_verification.get("result")
        cv_issues_list: list[dict] = []
        if clr and clr.success and clr.verified_claims:
            cv_issues_list = clr.to_cv_issues()
        elif cv_result and cv_result.success:
            # 降级: 使用旧的 cv_result
            for d in cv_result.discrepancies:
                judgment = d.judgment or ""
                is_issue = any(judgment.startswith(p) for p in ("⚠", "✗", "?"))
                if not is_issue:
                    continue
                cv_issues_list.append({
                    "dimension": d.dimension,
                    "judgment": judgment,
                    "web_evidence": d.evidence or "",
                    "evidence": d.evidence or "",
                    "suggestion": d.suggestion or "",
                })

        if cv_issues_list:
            print(f"\n[Phase 5c] 根因反思 (对 {len(cv_issues_list)} 个 CV 问题项做诊断)...")
            from src.llm.analysis_agent import AnalysisAgent as RCAgent
            try:
                rc_agent = RCAgent()
                root_cause_result = rc_agent.diagnose_root_cause(
                    cv_issues=cv_issues_list,
                    brief_md=brief_md,
                    company_name=bundle.name,
                    ts_code=args.ts_code,
                )
                if root_cause_result.success:
                    print(f"  诊断完成: 企业真实问题={root_cause_result.enterprise_issues_count} "
                          f"数据质量问题={root_cause_result.data_quality_issues_count} "
                          f"评估规则偏差={root_cause_result.methodology_issues_count} "
                          f"信息不足={root_cause_result.insufficient_info_count}")
                    if root_cause_result.summary:
                        print(f"  总结: {root_cause_result.summary[:120]}")
                    for item in root_cause_result.items[:3]:
                        print(f"    [{item.root_cause[:4]}] {item.dimension}: {item.reasoning[:80]}...")
                    if len(root_cause_result.items) > 3:
                        print(f"    ... 共 {len(root_cause_result.items)} 项")
                else:
                    print(f"  [WARN] 根因反思失败: {root_cause_result.error}")
            except Exception as e:
                print(f"  [WARN] 根因反思异常: {e}")
        else:
            print("\n[Phase 5c] 根因反思: 无 CV 问题项，跳过")

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
        clr = claim_verification.get("result")
        has_cv = (cv_result and cv_result.success) or (clr and clr.success)

        if has_cv:
            cv_output = output.replace(".html", "_cv.html")
            try:
                from src.llm.orchestrator import OrchestrationResult
                orch_result = OrchestrationResult(
                    ts_code=args.ts_code,
                    name=bundle.name,
                    final_score=result,
                    analysis=analysis_result,
                )
                # v0.30: 传递逐条核查结果
                gen.save_cross_validated(
                    result, cv_result, financial_insights, cv_output,
                    orch_result, root_cause_result,
                    claim_result=clr if clr and clr.success else None,
                )
                print(f"  交叉验证报告已保存: {cv_output}")
            except Exception as e:
                print(f"  [WARN] 交叉验证报告生成失败: {e}")
                import traceback
                traceback.print_exc()

    elif not args.no_llm and business_knowledge:
        # 无 --html 时也保存 brief.md（已在 Phase 4 保存）
        pass

    print("\n[DONE] Analysis complete.")


if __name__ == "__main__":
    main()

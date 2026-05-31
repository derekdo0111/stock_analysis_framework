"""
Jinja2 报告生成器 — 龟龟策略 HTML 分析报告。

输入: TurtleScorer FinalScore + Agent 分析/验证结果
输出: 自包含 HTML 报告
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from jinja2 import Environment, BaseLoader

from src.calculator.turtle_strategy.scoring import FinalScore
from src.llm.orchestrator import OrchestrationResult


_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>龟龟策略分析报告 — {{ name }} ({{ ts_code }})</title>
<style>
  :root { --bg:#0d1117; --card:#161b22; --border:#30363d; --text:#c9d1d9;
         --accent:#58a6ff; --green:#3fb950; --yellow:#d2991d; --red:#f85149; --purple:#a371f7; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,sans-serif; padding:24px; max-width:1000px; margin:0 auto; line-height:1.6; }
  h1 { font-size:2rem; }
  h2 { font-size:1.3rem; margin:24px 0 12px; border-bottom:1px solid var(--border); padding-bottom:8px; }
  .header { text-align:center; margin-bottom:32px; }
  .header .score { font-size:3rem; font-weight:700; }
  .pool-tag { display:inline-block; padding:4px 16px; border-radius:20px; font-size:0.9rem; font-weight:600; margin-left:12px; }
  .pool-core { background:#1a3a2a; color:var(--green); }
  .pool-watch { background:#3a2a0a; color:var(--yellow); }
  .pool-fallback { background:#1a1a2e; color:var(--text-dim); }

  .grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:16px; margin-bottom:24px; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:20px; }
  .card h3 { font-size:1rem; margin-bottom:8px; color:var(--accent); }

  .metric { display:flex; justify-content:space-between; padding:4px 0; font-size:0.9rem; }
  .metric-val { font-weight:600; }
  .metric-val.green { color:var(--green); }
  .metric-val.yellow { color:var(--yellow); }
  .metric-val.red { color:var(--red); }

  .module { border-left:2px solid var(--border); padding:8px 0 8px 12px; margin:8px 0; }
  .module.passed { border-left-color:var(--green); }
  .module.warning { border-left-color:var(--yellow); }
  .module.critical { border-left-color:var(--red); }
  .module .score { font-weight:700; font-size:0.9rem; }
  .module .evidence { font-size:0.85rem; color:var(--text-dim); margin-top:4px; }

  .flag { padding:6px 12px; border-radius:6px; margin:4px 0; font-size:0.85rem; }
  .flag-warn { background:#3a2a0a; color:var(--yellow); }
  .flag-crit { background:#3a0a0a; color:var(--red); }

  .pipeline { display:flex; gap:4px; margin:12px 0; flex-wrap:wrap; }
  .step { padding:4px 12px; border-radius:6px; font-size:0.78rem; }
  .step-done { background:#1a3a2a; }
  .step-pending { background:var(--border); }

  .footer { text-align:center; color:var(--text-dim); font-size:0.8rem; margin-top:48px; }
  .verdict { font-size:1.1rem; font-weight:600; padding:8px 0; }
</style>
</head>
<body>
<div class="header">
  <h1>{{ name }} <span style="color:var(--text-dim);font-size:0.8em;">{{ ts_code }}</span></h1>
  <div class="score {% if pool == '核心池' %}green{% elif pool == '观察池' %}yellow{% else %}red{% endif %}" style="color:{% if pool == '核心池' %}var(--green){% elif pool == '观察池' %}var(--yellow){% else %}var(--red){% endif %}">
    {{ final_score }}
  </div>
  <div class="pool-tag {% if pool == '核心池' %}pool-core{% elif pool == '观察池' %}pool-watch{% else %}pool-fallback{% endif %}">{{ pool }}</div>
</div>

<div class="grid">
  <div class="card">
    <h3>🏗️ 量化评分分解</h3>
    <div class="metric"><span>L2 初筛 (20pt)</span><span class="metric-val">{{ l2_score }}</span></div>
    <div class="metric"><span>L3 商业模式乘数</span><span class="metric-val">×{{ l3_multiplier }}</span></div>
    <div class="metric"><span>L4 穿透回报率 (40pt)</span><span class="metric-val {% if l4_score >= 20 %}green{% else %}yellow{% endif %}">{{ l4_score }}</span></div>
    <div class="metric"><span>L5 安全边际 (25pt)</span><span class="metric-val {% if l5_score >= 15 %}green{% else %}yellow{% endif %}">{{ l5_score }}</span></div>
    <div class="metric"><span>Raw Total</span><span class="metric-val">{{ raw_total }}</span></div>
    <div class="metric" style="font-weight:700;border-top:1px solid var(--border);padding-top:8px;"><span>Final Score</span><span class="metric-val green">{{ final_score }}</span></div>
  </div>

  <div class="card">
    <h3>📈 穿透回报率</h3>
    <div class="metric"><span>PR</span><span class="metric-val">{{ pr_pct }}%</span></div>
    <div class="metric"><span>OE 质量标签</span><span class="metric-val">{{ oe_quality }}</span></div>
    <div class="metric"><span>建议仓位上限</span><span class="metric-val">{{ position_pct }}%</span></div>
    {% if business_model %}
    <div class="metric"><span>商业模式判断</span><span class="metric-val">{{ business_model }}</span></div>
    {% endif %}
  </div>
</div>

{% if analysis %}
<h2>🧠 分析 Agent 输出</h2>
<div class="card" style="margin-bottom:12px;">
  <span style="color:var(--text-dim)">定性总分:</span> <strong>{{ analysis.qualitative_total }}/45</strong>
  <span style="margin-left:16px;color:var(--text-dim)">商业模式:</span> <strong>{{ analysis.business_model }}</strong>
</div>
{% for detail in analysis.module_details %}
<div class="module {% if loop.index is divisibleby 3 %}passed{% else %}passed{% endif %}">
  <div class="score">{{ detail.get('module','') }}: {{ detail.get('score','?') }}/5</div>
  <div class="evidence">{{ detail.get('evidence','')[:200] }}</div>
</div>
{% endfor %}
{% endif %}

{% if verification %}
<h2>🔍 验证 Agent — 审计结果</h2>
<div class="verdict" style="color:{% if verification.overall_verdict == '通过' %}var(--green){% else %}var(--yellow){% endif %}">
  裁决: {{ verification.overall_verdict }}
  {% if verification.requires_human_review %}<span style="color:var(--red)">⚠ 需人工审查</span>{% endif %}
</div>
<div class="metric"><span>事实核查通过率</span><span class="metric-val {% if verification.fact_check_pass_rate >= 80 %}green{% else %}yellow{% endif %}">{{ verification.fact_check_pass_rate }}%</span></div>
<p style="font-size:0.85rem;color:var(--text-dim);margin-top:8px;">{{ verification.executive_summary[:300] }}</p>
{% endif %}

{% if red_flags %}
<h2>🚩 红旗警告</h2>
{% for flag in red_flags %}
<div class="flag flag-warn">{{ flag }}</div>
{% endfor %}
{% endif %}

<div class="pipeline" style="margin-top:32px;">
  <div class="step step-done">HardGate ✓</div>
  <div class="step step-done">L2初筛</div>
  <div class="step step-done">公司分类</div>
  <div class="step step-done">OE双路径</div>
  <div class="step step-done">穿透回报率</div>
  <div class="step step-done">L5安全边际</div>
  <div class="step step-done">乘法打分</div>
</div>

<div class="footer">
  龟龟投资策略 v0.15 · 生成于 {{ generated_at }}<br>
  本报告仅供研究参考，不构成投资建议。
</div>
</body>
</html>"""


class ReportGenerator:
    """HTML 报告生成器。"""

    def generate(
        self,
        final_score: FinalScore,
        orchestration: OrchestrationResult | None = None,
    ) -> str:
        """生成自包含 HTML 分析报告。

        Returns:
            HTML 字符串
        """
        env = Environment(loader=BaseLoader())
        template = env.from_string(_REPORT_TEMPLATE)

        # 准备模板变量
        analysis_data = None
        verification_data = None
        red_flags = []

        if orchestration and orchestration.analysis:
            a = orchestration.analysis
            analysis_data = {
                "qualitative_total": a.qualitative_total,
                "business_model": a.business_model,
                "module_details": a.module_details,
            }
            red_flags = a.red_flags

        if orchestration and orchestration.verification:
            verification_data = {
                "overall_verdict": orchestration.verification.overall_verdict,
                "requires_human_review": orchestration.verification.requires_human_review,
                "fact_check_pass_rate": orchestration.verification.fact_check_pass_rate,
                "executive_summary": orchestration.verification.executive_summary,
                "fact_checks": orchestration.verification.fact_checks,
            }

        return template.render(
            ts_code=final_score.ts_code,
            name=final_score.name or final_score.ts_code,
            final_score=final_score.final_score,
            pool=final_score.pool,
            l2_score=final_score.l2_score,
            l3_multiplier=final_score.l3_multiplier,
            l4_score=final_score.l4_score,
            l5_score=final_score.l5_score,
            raw_total=final_score.raw_total,
            pr_pct=round(final_score.pr_pct, 2),
            oe_quality=final_score.oe_quality,
            position_pct=final_score.position_pct,
            business_model=final_score.business_model,
            analysis=analysis_data,
            verification=verification_data,
            red_flags=red_flags,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

    def save(self, final_score: FinalScore, path: str, orchestration: OrchestrationResult | None = None) -> str:
        """生成并保存报告到文件。"""
        html = self.generate(final_score, orchestration)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return html

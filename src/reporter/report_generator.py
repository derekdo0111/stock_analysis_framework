"""
Jinja2 报告生成器 — 完整龟龟策略 HTML 分析报告。

包含: 量化评分分解 / OE双路径详情 / PR+安全边际 / 9模块CFA分析(完整证据链)
      / 10项审计验证(逐条✓/✗+证据) / 红旗警告 / 管线步骤
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from jinja2 import Environment, BaseLoader

from src.calculator.turtle_strategy.scoring import FinalScore
from src.llm.orchestrator import OrchestrationResult


_REPORT_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>龟龟策略分析报告 — {{ name }} ({{ ts_code }})</title>
<style>
  :root { --bg:#0d1117; --card:#161b22; --border:#30363d; --text:#c9d1d9;
         --accent:#58a6ff; --green:#3fb950; --yellow:#d2991d; --red:#f85149; --purple:#a371f7;
         --text-dim:#8b949e; --orange:#db6d28; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; padding:32px; max-width:1100px; margin:0 auto; line-height:1.7; }
  h1 { font-size:2rem; }
  h2 { font-size:1.3rem; margin:32px 0 16px; border-bottom:1px solid var(--border); padding-bottom:10px; }
  h3 { font-size:1rem; margin:16px 0 8px; color:var(--accent); }

  .header { text-align:center; margin-bottom:40px; }
  .header .score { font-size:3.5rem; font-weight:700; }
  .pool-tag { display:inline-block; padding:6px 20px; border-radius:20px; font-size:0.95rem; font-weight:600; margin-left:16px; vertical-align:middle; }
  .pool-core { background:#1a3a2a; color:var(--green); }
  .pool-watch { background:#3a2a0a; color:var(--yellow); }
  .pool-fallback { background:#1a1a2e; color:var(--text-dim); }

  .grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); gap:16px; margin-bottom:24px; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:24px; }
  .card.full { grid-column:1/-1; }
  .card h3 { margin-top:0; }

  .metric { display:flex; justify-content:space-between; padding:5px 0; font-size:0.9rem; border-bottom:1px solid rgba(48,54,61,0.5); }
  .metric:last-child { border-bottom:none; }
  .metric-val { font-weight:600; }
  .metric-val.green { color:var(--green); }
  .metric-val.yellow { color:var(--yellow); }
  .metric-val.red { color:var(--red); }

  .bar-wrap { height:6px; background:var(--border); border-radius:3px; margin:4px 0 8px; overflow:hidden; }
  .bar-fill { height:100%; border-radius:3px; transition:width .5s; }
  .bar-fill.green { background:var(--green); }
  .bar-fill.yellow { background:var(--yellow); }
  .bar-fill.red { background:var(--red); }
  .bar-fill.blue { background:var(--accent); }

  .module { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; margin:10px 0; }
  .module .mod-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }
  .module .mod-name { font-weight:700; font-size:0.95rem; }
  .module .mod-score { font-weight:700; font-size:1.1rem; }
  .module .mod-confidence { font-size:0.78rem; padding:2px 8px; border-radius:10px; }
  .conf-high { background:#1a3a2a; color:var(--green); }
  .conf-medium { background:#3a2a0a; color:var(--yellow); }
  .conf-low { background:#3a0a0a; color:var(--red); }
  .module .evidence { font-size:0.88rem; color:var(--text); margin:8px 0; line-height:1.6; }
  .module .uncertainty { font-size:0.82rem; color:var(--text-dim); font-style:italic; }

  .check-item { padding:10px 14px; margin:6px 0; border-radius:6px; font-size:0.88rem; }
  .check-pass { background:#1a3a2a; border-left:3px solid var(--green); }
  .check-warn { background:#3a2a0a; border-left:3px solid var(--yellow); }
  .check-fail { background:#3a0a0a; border-left:3px solid var(--red); }
  .check-info { background:#1a1a2e; border-left:3px solid var(--accent); }
  .check-item .check-label { font-weight:600; }
  .check-item .check-evidence { font-size:0.82rem; color:var(--text-dim); margin-top:4px; }

  .flag { padding:10px 14px; border-radius:6px; margin:6px 0; font-size:0.88rem; }
  .flag-warn { background:#3a2a0a; color:var(--yellow); border-left:3px solid var(--yellow); }
  .flag-crit { background:#3a0a0a; color:var(--red); border-left:3px solid var(--red); }

  .verdict-box { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:20px; margin:16px 0; }
  .verdict-box .verdict-title { font-size:1.15rem; font-weight:700; margin-bottom:12px; }
  .verdict-summary { font-size:0.9rem; color:var(--text); line-height:1.7; }

  .pipeline { display:flex; gap:6px; margin:16px 0; flex-wrap:wrap; }
  .step { padding:6px 14px; border-radius:6px; font-size:0.8rem; font-weight:500; }
  .step-done { background:#1a3a2a; color:var(--green); }
  .step-active { background:#3a2a0a; color:var(--yellow); }

  .oe-box { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:20px; margin:12px 0; }
  .oe-box h4 { font-size:0.9rem; color:var(--accent); margin-bottom:10px; }
  .oe-row { display:flex; gap:24px; flex-wrap:wrap; }
  .oe-col { flex:1; min-width:200px; }

  .footer { text-align:center; color:var(--text-dim); font-size:0.82rem; margin-top:56px; padding-top:24px; border-top:1px solid var(--border); }

  @media (max-width:768px) { body { padding:16px; } .oe-row { flex-direction:column; } }
</style>
</head>
<body>

<!-- ======== HEADER ======== -->
<div class="header">
  <h1>{{ name }} <span style="color:var(--text-dim);font-size:0.7em;">{{ ts_code }}</span></h1>
  <div class="score" style="color:{% if pool=='核心池' %}var(--green){% elif pool=='观察池' %}var(--yellow){% else %}var(--red){% endif %}">
    {{ final_score }}
  </div>
  <span class="pool-tag {% if pool=='核心池' %}pool-core{% elif pool=='观察池' %}pool-watch{% else %}pool-fallback{% endif %}">{{ pool }}</span>
  <div style="margin-top:8px;color:var(--text-dim);font-size:0.85rem;">
    龟龟投资策略 v0.15 · {{ generated_at }}
  </div>
</div>

<!-- ======== SECTION 1: 量化评分 ======== -->
<h2>1. 量化评分分解</h2>
<div class="grid">
  <div class="card">
    <h3>五层打分模型</h3>
    <div class="metric"><span>L2 初筛</span><span class="metric-val">{{ l2_score }} / 20</span></div>
    <div class="bar-wrap"><div class="bar-fill blue" style="width:{{ (l2_score/20*100)|int }}%"></div></div>
    <div class="metric"><span>L3 商业模式乘数</span><span class="metric-val">× {{ l3_multiplier }}</span></div>
    <div class="metric"><span>L4 穿透回报率</span><span class="metric-val {% if l4_score>=20 %}green{% else %}yellow{% endif %}">{{ l4_score }} / 40</span></div>
    <div class="bar-wrap"><div class="bar-fill {% if l4_score>=20 %}green{% else %}yellow{% endif %}" style="width:{{ (l4_score/40*100)|int }}%"></div></div>
    <div class="metric"><span>L5 安全边际</span><span class="metric-val {% if l5_score>=15 %}green{% else %}yellow{% endif %}">{{ l5_score }} / 25</span></div>
    <div class="bar-wrap"><div class="bar-fill {% if l5_score>=15 %}green{% else %}yellow{% endif %}" style="width:{{ (l5_score/25*100)|int }}%"></div></div>
    <div class="metric" style="font-weight:700;border-top:1px solid var(--border);margin-top:8px;padding-top:10px;">
      <span>Final Score</span><span class="metric-val green">{{ final_score }} / 102</span>
    </div>
  </div>

  <div class="card">
    <h3>穿透回报率 & 仓位</h3>
    <div class="metric"><span>PR (OE_cf / 市值)</span><span class="metric-val {% if pr_pct>=8 %}green{% elif pr_pct>=5 %}yellow{% else %}red{% endif %}">{{ "%.2f"|format(pr_pct) }}%</span></div>
    <div class="metric"><span>OE 质量标签</span><span class="metric-val">{{ oe_quality }}</span></div>
    <div class="metric"><span>建议仓位上限</span><span class="metric-val">{{ position_pct }}%</span></div>
    <div class="metric"><span>商业模式判断</span><span class="metric-val">{{ business_model }}</span></div>
    {% if oe_details %}
    <div style="margin-top:12px;padding-top:8px;border-top:1px solid var(--border);">
      <div style="font-size:0.82rem;color:var(--text-dim);">
        OE_cf 中位数: {{ oe_details.oe_cf_median }} · CAPEX系数: {{ oe_details.mc }}
      </div>
    </div>
    {% endif %}
  </div>
</div>

<!-- ======== SECTION 2: OE 双路径计算详情 ======== -->
{% if oe_details %}
<h2>2. OE 双路径计算详情</h2>
<div class="oe-box">
  <div class="oe-row">
    <div class="oe-col">
      <h4>路径B (现金流 — 主路径)</h4>
      <div class="metric"><span>公式</span><span class="metric-val">经营CF - CAPEX × 系数</span></div>
      <div class="metric"><span>维持CAPEX系数</span><span class="metric-val">{{ oe_details.mc }}</span></div>
      <div class="metric"><span>OE_cf 5年中位数</span><span class="metric-val">{{ oe_details.oe_cf_median }}</span></div>
      <div class="metric"><span>OE_cf 均值</span><span class="metric-val">{{ oe_details.oe_cf_mean }}</span></div>
      <div class="metric"><span>变异系数 (CV)</span><span class="metric-val">{{ oe_details.oe_cf_cv }}</span></div>
      <div class="metric"><span>近3年 CAGR</span><span class="metric-val {% if oe_details.oe_cf_cagr>=0 %}green{% else %}red{% endif %}">{{ oe_details.oe_cf_cagr }}%</span></div>
    </div>
    <div class="oe-col">
      <h4>路径A (利润表 — 辅助验证)</h4>
      <div class="metric"><span>公式</span><span class="metric-val">净利润 + 折旧等 - 维持CAPEX</span></div>
      <div class="metric"><span>OE_income 中位数</span><span class="metric-val">{{ oe_details.oe_income_median }}</span></div>
      <div class="metric"><span>利润→现金转化率</span><span class="metric-val {% if oe_details.profit_to_cash>=1.0 %}green{% elif oe_details.profit_to_cash>=0.7 %}yellow{% else %}red{% endif %}">{{ oe_details.profit_to_cash }}</span></div>
      <div class="metric"><span>OE/净利润 比率</span><span class="metric-val {% if oe_details.oe_to_profit>=0.8 %}green{% elif oe_details.oe_to_profit>=0.5 %}yellow{% else %}red{% endif %}">{{ oe_details.oe_to_profit }}</span></div>
    </div>
  </div>
  <div style="margin-top:16px;">
    <h4>维持性CAPEX系数推导</h4>
    <div class="metric"><span>行业先验 (权重40%)</span><span class="metric-val">{{ oe_details.industry_prior }}</span></div>
    <div class="metric"><span>CAPEX/营收 5年均值</span><span class="metric-val">{{ oe_details.capex_rev_pct }}%</span></div>
    <div class="metric"><span>固定资产周转率</span><span class="metric-val">{{ oe_details.fixed_at }}</span></div>
    <div class="metric"><span>折旧/营收 5年均值</span><span class="metric-val">{{ oe_details.dep_rev_pct }}%</span></div>
    <div class="metric"><span>资产轻重得分 (权重60%)</span><span class="metric-val">{{ oe_details.asset_score }}</span></div>
    <div class="metric" style="font-weight:700;"><span>最终系数</span><span class="metric-val green">{{ oe_details.mc }}</span></div>
  </div>
</div>
{% endif %}

<!-- ======== SECTION 3: CFA 分析 Agent ======== -->
{% if analysis %}
<h2>3. CFA 分析 Agent — 9模块定性评估</h2>
<div class="card" style="margin-bottom:16px;">
  <div class="metric"><span>定性总分</span><span class="metric-val green">{{ analysis.qualitative_total }} / 45</span></div>
  <div class="metric"><span>商业模式判断</span><span class="metric-val">{{ analysis.business_model }}</span></div>
  {% if analysis.business_model_reasoning %}
  <div style="margin-top:10px;font-size:0.88rem;color:var(--text);line-height:1.6;">{{ analysis.business_model_reasoning }}</div>
  {% endif %}
</div>

{% for detail in analysis.module_details %}
<div class="module">
  <div class="mod-header">
    <span class="mod-name">{{ detail.get('module','') }}</span>
    <span>
      <span class="mod-confidence conf-{{ detail.get('confidence','medium') }}">{{ detail.get('confidence','medium') }}</span>
      <span class="mod-score" style="margin-left:8px;">{{ detail.get('score','?') }} / 5</span>
    </span>
  </div>
  <div class="evidence">{{ detail.get('evidence','') | replace('【','<br><br>【') | safe }}</div>
  {% if detail.get('uncertainty') %}
  <div class="uncertainty">⚠ 不确定因素: {{ detail.get('uncertainty') }}</div>
  {% endif %}
</div>
{% endfor %}
{% endif %}

<!-- ======== SECTION 4: CPA+CFE 验证 Agent ======== -->
{% if verification %}
<h2>4. CPA+CFE 审计验证</h2>
<div class="verdict-box">
  <div class="verdict-title">
    综合裁决: {{ verification.overall_verdict }}
    {% if verification.requires_human_review %}
    <span style="color:var(--red);">⚠ 需人工审查</span>
    {% endif %}
  </div>
  <div class="metric"><span>事实核查通过率</span><span class="metric-val {% if verification.fact_check_pass_rate>=80 %}green{% else %}yellow{% endif %}">{{ "%.0f"|format(verification.fact_check_pass_rate) }}%</span></div>
  <div class="bar-wrap"><div class="bar-fill {% if verification.fact_check_pass_rate>=80 %}green{% else %}yellow{% endif %}" style="width:{{ verification.fact_check_pass_rate|int }}%"></div></div>
  <div class="verdict-summary">{{ verification.executive_summary }}</div>
</div>

{% if verification.fact_checks %}
<h3>逐条事实核查</h3>
{% for check in verification.fact_checks %}
{% if check.get('verified') %}
<div class="check-item check-pass">
  <span class="check-label">✓ {{ check.get('module','') }}</span>
  <div style="font-size:0.85rem;">声明: {{ check.get('claim','') }}</div>
  <div class="check-evidence">{{ check.get('evidence','') }}</div>
</div>
{% elif check.get('severity','') == 'CRITICAL' %}
<div class="check-item check-fail">
  <span class="check-label">✗ CRITICAL — {{ check.get('module','') }}</span>
  <div style="font-size:0.85rem;">声明: {{ check.get('claim','') }}</div>
  <div class="check-evidence">{{ check.get('evidence','') }}</div>
</div>
{% elif check.get('severity','') == 'WARNING' %}
<div class="check-item check-warn">
  <span class="check-label">⚠ WARNING — {{ check.get('module','') }}</span>
  <div style="font-size:0.85rem;">声明: {{ check.get('claim','') }}</div>
  <div class="check-evidence">{{ check.get('evidence','') }}</div>
</div>
{% else %}
<div class="check-item check-info">
  <span class="check-label">ℹ {{ check.get('module','') }}</span>
  <div style="font-size:0.85rem;">{{ check.get('claim','') }}</div>
</div>
{% endif %}
{% endfor %}
{% endif %}

{% if verification.data_issues %}
<h3>数据问题发现</h3>
{% for issue in verification.data_issues %}
<div class="flag flag-{{ 'crit' if issue.get('severity')=='CRITICAL' else 'warn' }}">
  <strong>[{{ issue.get('audit_program','') }}]</strong> {{ issue.get('finding','') }}
  {% if issue.get('evidence') %}
  <div style="font-size:0.82rem;color:var(--text-dim);margin-top:4px;">证据: {{ issue.get('evidence') }}</div>
  {% endif %}
</div>
{% endfor %}
{% endif %}

{% if verification.consistency_flags %}
<h3>一致性矛盾</h3>
{% for cflag in verification.consistency_flags %}
<div class="flag flag-warn">
  <strong>{{ cflag.get('module_a','') }} ↔ {{ cflag.get('module_b','') }}:</strong> {{ cflag.get('contradiction','') }}
</div>
{% endfor %}
{% endif %}
{% endif %}

<!-- ======== SECTION 5: 红旗警告 ======== -->
{% if red_flags %}
<h2>5. 红旗警告</h2>
{% for flag in red_flags %}
<div class="flag flag-warn">🚩 {{ flag }}</div>
{% endfor %}
{% endif %}

<!-- ======== SECTION 6: 管线步骤 ======== -->
<h2>6. 处理管线</h2>
<div class="pipeline">
  <div class="step step-done">HardGate ✓</div>
  <div class="step step-done">L2初筛</div>
  <div class="step step-done">公司分类</div>
  <div class="step step-done">OE双路径</div>
  <div class="step step-done">穿透回报率</div>
  <div class="step step-done">L5安全边际</div>
  <div class="step step-done">乘法打分</div>
  <div class="step {% if analysis %}step-done{% endif %}">CFA分析</div>
  <div class="step {% if verification %}step-done{% endif %}">CPA验证</div>
</div>

<div class="footer">
  龟龟投资策略框架 v0.15<br>
  本报告仅供研究参考，不构成投资建议。<br>
  生成时间: {{ generated_at }}
</div>

</body>
</html>"""


class ReportGenerator:
    """HTML 报告生成器 — 完整分析报告。"""

    def generate(
        self,
        final_score: FinalScore,
        orchestration: OrchestrationResult | None = None,
        oe_details: dict[str, Any] | None = None,
    ) -> str:
        """生成完整 HTML 分析报告。"""
        env = Environment(loader=BaseLoader())
        template = env.from_string(_REPORT_TEMPLATE)

        analysis_data = None
        verification_data = None
        red_flags = []

        if orchestration and orchestration.analysis:
            a = orchestration.analysis
            analysis_data = {
                "qualitative_total": a.qualitative_total,
                "business_model": a.business_model,
                "business_model_reasoning": a.business_model_reasoning,
                "module_details": a.module_details,
            }
            red_flags = a.red_flags

        if orchestration and orchestration.verification:
            v = orchestration.verification
            verification_data = {
                "overall_verdict": v.overall_verdict,
                "requires_human_review": v.requires_human_review,
                "fact_check_pass_rate": v.fact_check_pass_rate,
                "executive_summary": v.executive_summary,
                "fact_checks": v.fact_checks,
                "data_issues": v.data_issues,
                "consistency_flags": v.consistency_flags,
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
            oe_details=oe_details,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

    def save(
        self,
        final_score: FinalScore,
        path: str,
        orchestration: OrchestrationResult | None = None,
        oe_details: dict[str, Any] | None = None,
    ) -> str:
        """生成并保存报告到文件。"""
        html = self.generate(final_score, orchestration, oe_details)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return html

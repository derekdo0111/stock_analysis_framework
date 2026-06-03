"""
Jinja2 报告生成器 — 完整龟龟策略 HTML 分析报告。

包含: HardGate / L2分解 / 公司分类 / OE详情 / PR逐年 / L5外推+陷阱 / 打分总结
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from jinja2 import Environment, BaseLoader

from src.calculator.turtle_strategy.scoring import FinalScore
from src.llm.client import LLMConfig
from src.llm.orchestrator import OrchestrationResult


class ReportGenerator:
    """HTML 报告生成器 — 从 FinalScore 富数据生成完整报告。"""

    def generate(self, final_score: FinalScore, orchestration: OrchestrationResult | None = None) -> str:
        """生成完整 HTML 分析报告。"""
        env = Environment(loader=BaseLoader())
        template = env.from_string(_TEMPLATE)
        return template.render(**self._build_context(final_score, orchestration))

    def save(self, final_score: FinalScore, path: str, orchestration: OrchestrationResult | None = None) -> str:
        """生成并保存报告到文件。"""
        html = self.generate(final_score, orchestration)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return html

    def _build_context(self, f: FinalScore, orch: OrchestrationResult | None = None) -> dict[str, Any]:
        l = lambda v, n: f"{v:.{n}f}"
        score_color = "var(--green)" if f.final_score >= 75 else ("var(--yellow)" if f.final_score >= 50 else "var(--red)")
        pool_class = {"核心池": "pool-core", "观察池": "pool-watch"}.get(f.pool, "pool-fallback")
        return {
            "name": f.name or f.ts_code,
            "ts_code": f.ts_code,
            "final_score": l(f.final_score, 2),
            "pool": f.pool,
            "pool_class": pool_class,
            "score_color": score_color,
            # ── v0.23: L3 商业模式 (0-30pt 加法) ──
            "l3_score": l(f.l3_score, 1),
            "l3_level": f.l3_level,
            "l3_total_dim": l(f.l3_total_dim, 1),
            "l3_dim_scores": f.l3_dim_scores,
            "l3_group_scores": f.l3_group_scores,
            "l3_bar_pct": int(f.l3_score / 30 * 100) if f.l3_score else 0,
            # ── L2 仅显示 ──
            "l2_score": l(f.l2_score, 1),
            "l2_bar_pct": int(f.l2_score / 20 * 100),
            "l2_details": f.l2_details,
            "l2_pool": f.l2_pool,
            # ── L4 穿透回报率 (0-45pt) ──
            "l4_score": l(f.l4_score, 1),
            "l4_bar_pct": int(f.l4_score / 45 * 100) if f.l4_score else 0,
            "l4_color": "green" if f.l4_score >= 22 else ("yellow" if f.l4_score >= 11 else "red"),
            # ── L5 安全边际 (0-25pt) ──
            "l5_score": l(f.l5_score, 1),
            "l5_bar_pct": int(f.l5_score / 25 * 100) if f.l5_score else 0,
            "l5_color": "green" if f.l5_score >= 15 else "yellow",
            "l5_safety_margin_pct": l(f.l5_safety_margin_pct, 1),
            "l5_safety_margin_color": "green" if f.l5_safety_margin_pct >= 30 else ("yellow" if f.l5_safety_margin_pct >= 0 else "red"),
            "l5_reasonable_mv": l(f.l5_reasonable_mv / 1e8, 1) if f.l5_reasonable_mv else "N/A",
            "l5_valuation_score": l(f.l5_valuation_score, 1),
            "l5_downside_score": l(f.l5_downside_score, 1),
            "l5_downside_details": f.l5_downside_details,
            "l5_position_score": l(f.l5_position_score, 1) if hasattr(f, 'l5_position_score') else "0",
            "position_pct": l(f.position_pct, 1),
            # ── PR 详情 ──
            "pr_pct": l(f.pr_pct, 2),
            "pr_color": "green" if f.pr_pct >= 8 else ("yellow" if f.pr_pct >= 5 else "red"),
            "oe_quality": f.oe_quality,
            "hard_gate_passed": f.hard_gate_passed,
            "hard_gate_checks": f.hard_gate_checks,
            "classify_type": f.classify_type,
            "classify_reason": f.classify_reason,
            "pr_starting_score": l(f.pr_starting_score, 1),
            "pr_quality_penalty": l(f.pr_quality_penalty, 1),
            "pr_disposable_cash": l(f.pr_disposable_cash / 1e4, 1) if f.pr_disposable_cash else "N/A",
            "pr_distribution_ratio": l(f.pr_distribution_ratio, 1),
            "pr_distribution_source": "公告承诺" if "tier1" in f.pr_distribution_source else "历史外推",
            "pr_buyback_cancellation": l(f.pr_buyback_cancellation / 1e4, 1) if f.pr_buyback_cancellation else "0",
            "oe_cf_median": l(float(f.oe_cf_median) / 1e4, 1) if f.oe_cf_median else "N/A",
            "oe_path_b_values": [l(v / 1e4, 1) for v in f.oe_path_b_values] if f.oe_path_b_values else [],
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            # Agent 分析
            "has_agent": orch is not None and orch.analysis is not None,
            "agent_total": orch.analysis.qualitative_total if (orch and orch.analysis) else 0,
            "agent_model": orch.analysis.business_model if (orch and orch.analysis) else "",
            "agent_reasoning": orch.analysis.business_model_reasoning if (orch and orch.analysis) else "",
            "agent_modules": orch.analysis.module_details if (orch and orch.analysis) else [],
            "agent_red_flags": orch.analysis.red_flags if (orch and orch.analysis) else [],
            "agent_source": "[本地规则引擎]" if (orch and orch.analysis and not LLMConfig.is_configured()) else "[LLM]",
            "verification_verdict": orch.verification.overall_verdict if (orch and orch.verification) else "",
        }


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>龟龟策略分析报告 — {{ name }} ({{ ts_code }})</title>
<style>
  :root { --bg:#0d1117; --card:#161b22; --border:#30363d; --text:#c9d1d9;
         --accent:#58a6ff; --green:#3fb950; --yellow:#d2991d; --red:#f85149;
         --text-dim:#8b949e; --orange:#db6d28; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; padding:32px; max-width:1100px; margin:0 auto; line-height:1.7; }
  h2 { font-size:1.25rem; margin:36px 0 16px; border-bottom:1px solid var(--border); padding-bottom:10px; }
  h3 { font-size:1rem; margin:16px 0 8px; color:var(--accent); }
  .header { text-align:center; margin-bottom:40px; }
  .header .score { font-size:3.5rem; font-weight:700; color:{{ score_color }}; }
  .pool-tag { display:inline-block; padding:6px 20px; border-radius:20px; font-size:0.95rem; font-weight:600; margin-left:12px; vertical-align:middle; }
  .pool-core { background:#1a3a2a; color:var(--green); }
  .pool-watch { background:#3a2a0a; color:var(--yellow); }
  .pool-fallback { background:#1a1a2e; color:var(--text-dim); }
  .grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); gap:16px; margin-bottom:24px; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:20px; }
  .card h3 { margin-top:0; }
  .metric { display:flex; justify-content:space-between; padding:5px 0; font-size:0.88rem; border-bottom:1px solid rgba(48,54,61,0.4); }
  .metric:last-child { border-bottom:none; }
  .metric-val { font-weight:600; text-align:right; }
  .bar-wrap { height:6px; background:var(--border); border-radius:3px; margin:4px 0 8px; overflow:hidden; }
  .bar-fill { height:100%; border-radius:3px; }
  .bar-fill.blue { background:var(--accent); }
  .bar-fill.green { background:var(--green); }
  .bar-fill.yellow { background:var(--yellow); }
  .bar-fill.red { background:var(--red); }
  .check-item { padding:10px 14px; margin:4px 0; border-radius:6px; font-size:0.85rem; }
  .check-pass { background:#1a3a2a; border-left:3px solid var(--green); }
  .check-fail { background:#3a0a0a; border-left:3px solid var(--red); }
  table { width:100%; border-collapse:collapse; font-size:0.85rem; margin-top:8px; }
  th,td { padding:7px 10px; text-align:left; border-bottom:1px solid var(--border); }
  th { color:var(--text-dim); font-weight:500; font-size:0.8rem; }
  td { font-variant-numeric:tabular-nums; }
  .flag { padding:10px 14px; border-radius:6px; margin:4px 0; font-size:0.85rem; }
  .flag-warn { background:#3a2a0a; border-left:3px solid var(--yellow); }
  .pipeline { display:flex; gap:6px; margin:16px 0; flex-wrap:wrap; }
  .step { padding:6px 14px; border-radius:6px; font-size:0.78rem; font-weight:500; }
  .step-done { background:#1a3a2a; color:var(--green); }
  .step-skip { background:#1a1a2e; color:var(--text-dim); }
  .footer { text-align:center; color:var(--text-dim); font-size:0.82rem; margin-top:56px; padding-top:24px; border-top:1px solid var(--border); }
</style>
</head>
<body>

<div class="header">
  <h1>{{ name }} <span style="color:var(--text-dim);font-size:0.7em;">{{ ts_code }}</span></h1>
  <div class="score">{{ final_score }}</div>
  <span class="pool-tag {{ pool_class }}">{{ pool }}</span>
  <div style="margin-top:8px;color:var(--text-dim);font-size:0.85rem;">龟龟投资策略 v0.23 · {{ generated_at }}</div>
</div>

<!-- ====== 1. HardGate 否决检查 ====== -->
<h2>1. HardGate 否决检查</h2>
{% if hard_gate_checks %}
<div class="grid">
  {% for c in hard_gate_checks %}
  <div class="check-item {% if c.passed %}check-pass{% else %}check-fail{% endif %}">
    <strong>{% if c.passed %}PASS{% else %}VETO{% endif %}</strong> &nbsp; {{ c.name }}
    {% if c.value %}<span style="color:var(--text-dim);margin-left:8px;">= {{ c.value }}</span>{% endif %}
  </div>
  {% endfor %}
</div>
{% else %}
<div class="card"><span style="color:var(--text-dim);">HardGate 数据未捕获（旧版打分器）</span></div>
{% endif %}

<!-- ====== 2. L2 初筛 + 公司分类 ====== -->
<h2>2. L2 初筛 (门控) &amp; 公司分类</h2>
<div class="grid">
  <div class="card">
    <h3>L2 初筛 (仅门控, 不参与最终评分)</h3>
    <div class="metric"><span>财务质量</span><span class="metric-val">{{ l2_details.get('financial_quality','-') }} / 9</span></div>
    <div class="metric"><span>估值合理性</span><span class="metric-val">{{ l2_details.get('valuation','-') }} / 6</span></div>
    <div class="metric"><span>流动性健康</span><span class="metric-val">{{ l2_details.get('liquidity','-') }} / 3</span></div>
    <div class="metric"><span>加分项</span><span class="metric-val">{{ l2_details.get('bonus','-') }} / 2</span></div>
    <div class="metric" style="font-weight:700;border-top:1px solid var(--border);margin-top:6px;padding-top:6px;">
      <span>L2 总分 (仅供参考)</span><span class="metric-val">{{ l2_score }} / 20</span>
    </div>
    <div style="margin-top:8px;font-size:0.82rem;color:var(--text-dim);">分流: {{ l2_pool }}</div>
  </div>
  <div class="card">
    <h3>公司分类</h3>
    <div class="metric"><span>分类</span><span class="metric-val green">{{ classify_type }}</span></div>
    {% if classify_reason %}<div style="margin-top:10px;font-size:0.85rem;color:var(--text-dim);">{{ classify_reason }}</div>{% endif %}
  </div>
</div>

<!-- ====== 3. 穿透回报率 (L4, 0-45pt) ====== -->
<h2>3. 穿透回报率 (L4) — 核心估值</h2>
<div class="grid">
  <div class="card">
    <h3>OE 概要 (路径B)</h3>
    <div class="metric"><span>OE_cf 中位数</span><span class="metric-val">{{ oe_cf_median }} 亿</span></div>
    <div class="metric"><span>OE 质量标签</span><span class="metric-val">{{ oe_quality }}</span></div>
    {% if oe_path_b_values %}
    <div class="metric"><span>OE_cf 近5年</span><span class="metric-val">{{ oe_path_b_values|join(', ') }} 亿</span></div>
    {% endif %}
  </div>
  <div class="card">
    <h3>L4 打分 (0-45pt)</h3>
    <div class="metric"><span>PR (穿透回报率)</span><span class="metric-val {{ pr_color }}">{{ pr_pct }}%</span></div>
    <div class="metric"><span>起点分</span><span class="metric-val">{{ pr_starting_score }}</span></div>
    <div class="metric"><span>质量扣分</span><span class="metric-val red">{{ pr_quality_penalty }}</span></div>
    <div class="metric" style="font-weight:700;border-top:1px solid var(--border);margin-top:6px;padding-top:6px;">
      <span>L4 最终得分</span><span class="metric-val {{ l4_color }}">{{ l4_score }} / 45</span>
    </div>
    <div class="bar-wrap"><div class="bar-fill {{ l4_color }}" style="width:{{ l4_bar_pct }}%"></div></div>
  </div>
</div>

<h3>v0.22 PR 公式展开</h3>
<div class="card" style="overflow-x:auto;">
  <div style="font-size:0.85rem;color:var(--accent);margin-bottom:12px;">
    PR = (可支配现金 &times; 分配比率 + 回购注销) / 当前市值
  </div>
  <table>
    <tr><th>组件</th><th>值</th><th>来源</th></tr>
    <tr>
      <td>当前可支配现金</td>
      <td>{{ pr_disposable_cash }} 亿</td>
      <td style="color:var(--text-dim);">经营CF - 维持性CAPEX - 并购子公司 - 参股净增 - 财务费用 + 货币资金 - 限制性货币 - 短期借款 + 交易性金融资产</td>
    </tr>
    <tr>
      <td>分配比率</td>
      <td>{{ pr_distribution_ratio }}%</td>
      <td style="color:var(--text-dim);">{{ pr_distribution_source }}</td>
    </tr>
    <tr>
      <td>回购注销金额</td>
      <td>{{ pr_buyback_cancellation }} 亿</td>
      <td style="color:var(--text-dim);">Web搜索+LLM提取</td>
    </tr>
    <tr style="font-weight:700;border-top:2px solid var(--border);">
      <td>PR (穿透回报率)</td>
      <td style="color:{{ pr_color }};">{{ pr_pct }}%</td>
      <td></td>
    </tr>
  </table>
  <div style="margin-top:12px;padding:10px 14px;background:#3a2a0a;border-left:3px solid var(--yellow);border-radius:6px;font-size:0.82rem;color:var(--yellow);">
    注：持股不足1个月需缴纳10%红利税，PR 未预先扣除。
  </div>
</div>

<!-- ====== 4. L5 估值安全边际 (v0.23) ====== -->
<h2>4. 安全边际 (L5) — 纯估值保护</h2>
<div class="grid">
  <div class="card">
    <h3>估值安全边际率 (0-15分)</h3>
    <div class="metric"><span>合理市值 (折现率7%)</span><span class="metric-val">{{ l5_reasonable_mv }} 亿</span></div>
    <div class="metric"><span>安全边际率</span><span class="metric-val {{ l5_safety_margin_color }}">{{ l5_safety_margin_pct }}%</span></div>
    <div class="metric" style="font-weight:700;border-top:1px solid var(--border);margin-top:6px;padding-top:6px;">
      <span>估值安全得分</span><span class="metric-val">{{ l5_valuation_score }} / 15</span>
    </div>
  </div>
  <div class="card">
    <h3>下行风险缓冲 (0-5分)</h3>
    {% if l5_downside_details %}
    {% for d in l5_downside_details %}
    <div class="metric"><span>{{ d.name }}</span><span class="metric-val">{{ "%.1f"|format(d.score) }}</span></div>
    <div style="font-size:0.75rem;color:var(--text-dim);margin-bottom:4px;">{{ d.label }}</div>
    {% endfor %}
    {% endif %}
    <div class="metric" style="font-weight:700;border-top:1px solid var(--border);margin-top:6px;padding-top:6px;">
      <span>缓冲得分</span><span class="metric-val">{{ l5_downside_score }} / 5</span>
    </div>
  </div>
</div>
<div class="grid">
  <div class="card">
    <h3>仓位矩阵 (0-5分)</h3>
    <div class="metric"><span>仓位上限</span><span class="metric-val">{{ position_pct }}%</span></div>
    <div class="metric"><span>仓位得分</span><span class="metric-val">{{ l5_position_score }} / 5</span></div>
    <div class="metric" style="font-weight:700;border-top:1px solid var(--border);margin-top:6px;padding-top:6px;">
      <span>L5 最终得分</span><span class="metric-val {{ l5_color }}">{{ l5_score }} / 25</span>
    </div>
    <div class="bar-wrap"><div class="bar-fill {{ l5_color }}" style="width:{{ l5_bar_pct }}%"></div></div>
  </div>
</div>

<!-- ====== 5. L3 商业模式详情 ====== -->
<h2>5. L3 商业模式评估 — 十二维</h2>
<div class="grid">
  <div class="card" style="grid-column:1/-1;">
    <h3>L3 得分: {{ l3_score }} / 30 &nbsp;|&nbsp; 等级: {{ l3_level }} &nbsp;|&nbsp; 维度分: {{ l3_total_dim }} / 24</h3>
    <div class="bar-wrap"><div class="bar-fill green" style="width:{{ l3_bar_pct }}%"></div></div>
  </div>
  {% if l3_dim_scores %}
  {% for id, d in l3_dim_scores.items() %}
  <div class="card">
    <h3>{{ d.name }} <span style="font-size:0.75rem;color:var(--text-dim);">({{ d.group }})</span></h3>
    <div class="metric"><span>得分</span><span class="metric-val">{{ "%.0f"|format(d.score) }} / 2</span></div>
    <div style="font-size:0.82rem;color:var(--text-dim);">{% if d.label %}{{ d.label }}{% endif %}</div>
  </div>
  {% endfor %}
  {% endif %}
</div>

<!-- ====== 6. 打分汇总 ====== -->
<h2>6. 打分汇总 — v0.23 百分制</h2>
<div class="grid">
  <div class="card" style="grid-column:1/-1;">
    <h3>Final = L3 + L4 + L5 = {{ l3_score }} + {{ l4_score }} + {{ l5_score }}</h3>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;text-align:center;margin-top:12px;">
      <div style="background:var(--bg);padding:14px;border-radius:8px;">
        <div style="font-size:0.78rem;color:var(--text-dim);">L3 商业模式</div>
        <div style="font-size:1.3rem;font-weight:700;color:var(--green);">{{ l3_score }}</div>
        <div style="font-size:0.7rem;color:var(--text-dim);">/30</div>
      </div>
      <div style="background:var(--bg);padding:14px;border-radius:8px;">
        <div style="font-size:0.78rem;color:var(--text-dim);">L4 穿透回报率</div>
        <div style="font-size:1.3rem;font-weight:700;color:{{ l4_color }};">{{ l4_score }}</div>
        <div style="font-size:0.7rem;color:var(--text-dim);">/45</div>
      </div>
      <div style="background:var(--bg);padding:14px;border-radius:8px;">
        <div style="font-size:0.78rem;color:var(--text-dim);">L5 安全边际</div>
        <div style="font-size:1.3rem;font-weight:700;color:{{ l5_color }};">{{ l5_score }}</div>
        <div style="font-size:0.7rem;color:var(--text-dim);">/25</div>
      </div>
      <div style="background:rgba(88,166,255,0.1);padding:14px;border-radius:8px;border:1px solid var(--accent);">
        <div style="font-size:0.78rem;color:var(--text-dim);">最终得分</div>
        <div style="font-size:1.6rem;font-weight:700;color:{{ score_color }};">{{ final_score }}</div>
        <div style="font-size:0.7rem;color:var(--text-dim);">{{ pool }}</div>
      </div>
    </div>
  </div>
</div>

<!-- ====== 7. 管线 ====== -->
<h2>7. 处理管线 — v0.23</h2>
<div class="pipeline">
  <div class="step step-done">HardGate</div>
  <div class="step step-done">L2门控</div>
  <div class="step step-done">公司分类</div>
  <div class="step step-done">L3十二维</div>
  <div class="step step-done">穿透回报率</div>
  <div class="step step-done">L5估值安全</div>
  <div class="step step-done">加法百分制</div>
  <div class="step {% if has_agent %}step-done{% else %}step-skip{% endif %}">Agent分析</div>
  <div class="step {% if verification_verdict %}step-done{% else %}step-skip{% endif %}">Agent验证</div>
</div>

<!-- ====== 8. Agent 分析 ====== -->
{% if has_agent %}
<h2>8. Agent 定性分析 {{ agent_source }}</h2>
<div class="grid">
  <div class="card" style="grid-column:1/-1;">
    <h3>商业模式判断: {{ agent_model }} · 总分 {{ agent_total }}/45</h3>
    <div style="font-size:0.85rem;color:var(--text-dim);margin-bottom:12px;">{{ agent_reasoning }}</div>
  </div>
  {% for m in agent_modules %}
  <div class="card">
    <h3>{{ m.module }}: {{ m.score }}/5
      <span style="font-size:0.75rem;color:var(--text-dim);margin-left:6px;">({{ m.confidence }})</span>
    </h3>
    <div style="font-size:0.82rem;white-space:pre-line;line-height:1.8;color:var(--text-dim);margin-top:8px;">{{ m.evidence }}</div>
    {% if m.uncertainty %}
    <div style="font-size:0.78rem;color:var(--yellow);margin-top:8px;padding:8px;background:#3a2a0a;border-radius:6px;">
      ⚠ {{ m.uncertainty }}
    </div>
    {% endif %}
  </div>
  {% endfor %}
</div>
{% if agent_red_flags %}
<h3>红旗警告</h3>
{% for rf in agent_red_flags %}
<div class="flag flag-warn">{{ rf }}</div>
{% endfor %}
{% endif %}
{% endif %}

<div class="footer">
  龟龟投资策略框架 v0.23 · 本报告仅供研究参考，不构成投资建议。<br>
  生成时间: {{ generated_at }}
</div>
</body></html>"""

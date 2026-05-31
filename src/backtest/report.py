"""
回测报告生成器 — HTML 报告。

核心对比: 股息回报 vs 无风险利率
"""

from __future__ import annotations

from datetime import datetime

from jinja2 import Environment, BaseLoader

from src.backtest.statistics import WindowStats, GroupStats


_BACKTEST_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>龟龟策略回测报告</title>
<style>
  :root { --bg:#0d1117; --card:#161b22; --border:#30363d; --text:#c9d1d9;
         --green:#3fb950; --yellow:#d2991d; --red:#f85149; --accent:#58a6ff;
         --text-dim:#8b949e; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,sans-serif; padding:32px; max-width:1200px; margin:0 auto; line-height:1.7; }
  h1 { font-size:2rem; margin-bottom:8px; }
  h2 { font-size:1.3rem; margin:32px 0 16px; border-bottom:1px solid var(--border); padding-bottom:8px; }
  .subtitle { color:var(--text-dim); margin-bottom:32px; }

  .grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:16px; margin-bottom:24px; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:20px; }
  .card h3 { font-size:1rem; color:var(--accent); margin-bottom:12px; }

  .metric { display:flex; justify-content:space-between; padding:4px 0; font-size:0.9rem; }
  .metric-val { font-weight:600; }
  .metric-val.green { color:var(--green); }
  .metric-val.red { color:var(--red); }
  .metric-val.yellow { color:var(--yellow); }

  .bar-wrap { height:6px; background:var(--border); border-radius:3px; margin:4px 0; overflow:hidden; }
  .bar-fill { height:100%; border-radius:3px; }
  .bar-fill.green { background:var(--green); }

  table { width:100%; border-collapse:collapse; font-size:0.88rem; margin:16px 0; }
  th, td { text-align:left; padding:10px 12px; border-bottom:1px solid var(--border); }
  th { color:var(--text-dim); font-weight:600; }

  .verdict { font-size:1.2rem; font-weight:700; padding:16px 0; }
  .footer { text-align:center; color:var(--text-dim); font-size:0.82rem; margin-top:48px; padding-top:24px; border-top:1px solid var(--border); }
</style>
</head>
<body>
<h1>龟龟策略 v0.15 — 回测验证报告</h1>
<p class="subtitle">验证哲学: 只验分红，不碰股价 · 对比基准: 无风险利率(国债收益率)</p>

<!-- ====== OVERVIEW ====== -->
<div class="grid">
  <div class="card">
    <h3>回测总览</h3>
    <div class="metric"><span>回测窗口数</span><span class="metric-val">{{ total_windows }}</span></div>
    <div class="metric"><span>跨窗口平均 Win Rate</span><span class="metric-val {% if cross_window.win_rate>50 %}green{% else %}red{% endif %}">{{ "%.1f"|format(cross_window.win_rate) }}%</span></div>
    <div class="metric"><span>跨窗口 PR 兑现率(中位数)</span><span class="metric-val {% if cross_window.avg_fulfillment>=0.7 %}green{% else %}yellow{% endif %}">{{ "%.2f"|format(cross_window.avg_fulfillment) }}</span></div>
  </div>
  <div class="card">
    <h3>判定标准</h3>
    <div class="metric"><span>PR 兑现率 ≥ 0.7</span><span class="metric-val green">PR 预测合格</span></div>
    <div class="metric"><span>股息回报 &gt; 无风险利率</span><span class="metric-val green">策略有效</span></div>
    <div class="metric"><span>Top5 - Bottom5 股息差 &gt; 0</span><span class="metric-val green">打分区分度</span></div>
  </div>
</div>

<!-- ====== WINDOW DETAILS ====== -->
<h2>各窗口详情</h2>
<table>
  <tr>
    <th>窗口</th>
    <th>股票数</th>
    <th>平均PR%</th>
    <th>PR兑现率</th>
    <th>Win Rate</th>
    <th>超额</th>
    <th>Top5股息</th>
    <th>Bottom5股息</th>
    <th>Spread</th>
  </tr>
  {% for s in window_stats %}
  <tr>
    <td>{{ s.window_label }}</td>
    <td>{{ s.total_stocks }}</td>
    <td>{{ "%.1f"|format(s.avg_pr_pct) }}%</td>
    <td><span style="color:{% if s.avg_fulfillment>=0.7 %}var(--green){% else %}var(--yellow){% endif %}">{{ "%.2f"|format(s.avg_fulfillment) }}</span></td>
    <td><span style="color:{% if s.win_rate>=50 %}var(--green){% else %}var(--red){% endif %}">{{ "%.0f"|format(s.win_rate) }}%</span></td>
    <td>{{ "%.1f"|format(s.avg_excess) }}%</td>
    <td>{{ "%.2f"|format(s.top5_avg_dividend) }}%</td>
    <td>{{ "%.2f"|format(s.bottom5_avg_dividend) }}%</td>
    <td style="color:{% if s.spread>0 %}var(--green){% else %}var(--red){% endif %}">{{ "%.2f"|format(s.spread) }}%</td>
  </tr>
  {% endfor %}
</table>

<!-- ====== VERDICT ====== -->
<div class="verdict" style="color:{% if cross_window.win_rate>50 %}var(--green){% else %}var(--yellow){% endif %}">
  {% if cross_window.win_rate > 50 %}
  ✅ 龟龟策略跨窗口验证: 策略有效
  {% else %}
  ⚠ 龟龟策略跨窗口验证: 需进一步优化
  {% endif %}
</div>

<div class="footer">
  龟龟投资策略框架 v0.15 · 生成于 {{ generated_at }}<br>
  验证哲学: 只验分红，不碰股价 · 对比基准: 中国10年期国债收益率
</div>
</body>
</html>"""


class BacktestReportGenerator:
    """回测报告生成器。"""

    def generate(
        self,
        window_stats: list[WindowStats],
        cross_window: GroupStats,
    ) -> str:
        env = Environment(loader=BaseLoader())
        template = env.from_string(_BACKTEST_TEMPLATE)
        return template.render(
            total_windows=len(window_stats),
            window_stats=window_stats,
            cross_window=cross_window,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

    def save(self, window_stats: list[WindowStats], cross_window: GroupStats, path: str) -> str:
        html = self.generate(window_stats, cross_window)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return html

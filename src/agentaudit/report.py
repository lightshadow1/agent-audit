"""HTML report generator for AgentAudit.

Produces a single self-contained HTML file (inline CSS, no external deps)
that surfaces the Article 12 evidence picture honestly: which checks the
trace data supports, which it cannot, and what artifacts are needed for
the rest.
"""

from __future__ import annotations

from typing import Any

import jinja2

from agentaudit import __version__
from agentaudit.article12 import RULES
from agentaudit.models import CheckStatus, Report

_CSS = """
:root {
  --c-met: #16a34a;
  --c-partial: #ca8a04;
  --c-not-met: #dc2626;
  --c-not-evidenced: #6b7280;
  --bg: #ffffff;
  --fg: #0f172a;
  --muted: #475569;
  --rule: #e2e8f0;
  --card: #f8fafc;
  --accent: #1e3a8a;
}
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  color: var(--fg);
  background: var(--bg);
  margin: 0;
  padding: 32px 24px 64px;
  line-height: 1.5;
}
.container { max-width: 960px; margin: 0 auto; }
header h1 { font-size: 28px; margin: 0 0 4px; }
.meta { color: var(--muted); font-size: 14px; margin: 0 0 24px; }
section { margin: 32px 0; }
h2 { font-size: 20px; border-bottom: 1px solid var(--rule); padding-bottom: 6px; }
h3 { font-size: 16px; margin: 0 0 8px; }
.dim, .muted { color: var(--muted); }
.honesty {
  background: #eef2ff;
  border-left: 4px solid var(--accent);
  padding: 16px 20px;
  border-radius: 4px;
}
.honesty h2 { border: none; padding: 0; margin: 0 0 8px; font-size: 18px; }
.honesty .disclaimer { font-size: 13px; color: var(--muted); margin-top: 8px; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--rule); }
th { font-weight: 600; background: var(--card); }
.badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  color: white;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.badge-met { background: var(--c-met); }
.badge-partial { background: var(--c-partial); }
.badge-not_met { background: var(--c-not-met); }
.badge-not_evidenced { background: var(--c-not-evidenced); }
.ev {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  border: 1px solid var(--rule);
  color: var(--muted);
  margin-left: 6px;
}
.ev-fully { color: var(--c-met); border-color: var(--c-met); }
.ev-partially { color: var(--c-partial); border-color: var(--c-partial); }
.ev-not-from-traces { color: var(--c-not-met); border-color: var(--c-not-met); }
.check {
  background: var(--card);
  border-left: 4px solid var(--rule);
  padding: 16px 20px;
  margin: 12px 0;
  border-radius: 4px;
}
.check-met { border-left-color: var(--c-met); }
.check-partial { border-left-color: var(--c-partial); }
.check-not_met { border-left-color: var(--c-not-met); }
.check-not_evidenced { border-left-color: var(--c-not-evidenced); }
.evidence { padding-left: 20px; margin: 8px 0; font-size: 14px; }
.evidence li { margin: 4px 0; }
.gap, .rem { font-size: 14px; margin: 6px 0; }
.gap strong { color: var(--c-not-met); }
.rem strong { color: var(--accent); }
.summary-stats {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin: 12px 0;
}
.stat {
  background: var(--card);
  border: 1px solid var(--rule);
  padding: 10px 16px;
  border-radius: 4px;
  min-width: 120px;
}
.stat .num { font-size: 22px; font-weight: 700; }
.stat .lbl { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
footer { margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--rule); font-size: 12px; color: var(--muted); }
.not-evidenceable ul { padding-left: 20px; }
.not-evidenceable li { margin: 6px 0; }
@media print {
  body { padding: 0; }
  .check { break-inside: avoid; }
}
"""

_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AgentAudit — EU AI Act Article 12 Evidence Report</title>
<style>{{ css }}</style>
</head>
<body>
<div class="container">
<header>
  <h1>EU AI Act Article 12 — Evidence Report</h1>
  <p class="meta">
    Generated {{ rep.generated_at.strftime('%Y-%m-%d %H:%M UTC') }} ·
    {{ rep.traces_analyzed }} traces · {{ rep.spans_analyzed }} spans ·
    Period {{ rep.period_start.date() }} to {{ rep.period_end.date() }}
  </p>
</header>

<section class="honesty">
  <h2>Scope of evidence</h2>
  <p>This report evaluates EU AI Act Article 12 evidence
    <strong>derivable from OpenTelemetry GenAI traces alone</strong>.
    {{ counts.met }} of {{ rep.checks | length }} trace-evidenceable checks passed
    ({{ counts.partial }} partial, {{ counts.not_met }} not met, {{ counts.not_evidenced }} not evidenced).</p>
  <p>Article 12 contains sub-requirements that no tracing tool can evidence —
    risk management documentation, quality management records,
    technical documentation under Annex IV, component identification under EN 18229-1.
    Those are listed in <em>Not trace-evidenceable</em> below and require
    separate artifacts.</p>
  <p class="disclaimer">This is not legal advice and does not certify compliance.
    It provides auditable evidence for the subset of Article 12 requirements
    that trace data can demonstrate, and explicitly names the subset it cannot.</p>
</section>

<section>
  <h2>Summary</h2>
  <div class="summary-stats">
    <div class="stat"><div class="num">{{ rep.traces_analyzed }}</div><div class="lbl">Traces</div></div>
    <div class="stat"><div class="num">{{ rep.spans_analyzed }}</div><div class="lbl">Spans</div></div>
    <div class="stat"><div class="num">{{ counts.met }}/{{ rep.checks | length }}</div><div class="lbl">Met</div></div>
    <div class="stat"><div class="num">{{ counts.not_met + counts.partial }}</div><div class="lbl">Need work</div></div>
  </div>
  <table>
    <thead><tr><th>Check</th><th>Article</th><th>Status</th><th>Evidenceability</th></tr></thead>
    <tbody>
    {% for c in rep.checks %}
      <tr>
        <td>{{ c.name }}</td>
        <td class="dim">{{ c.article }}</td>
        <td><span class="badge badge-{{ c.status.value }}">{{ c.status.value | replace('_', ' ') }}</span></td>
        <td class="dim">{{ c.evidenceability.value }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</section>

<section>
  <h2>Per-check evidence</h2>
  {% for c in rep.checks %}
  <article class="check check-{{ c.status.value }}">
    <h3>{{ c.name }} <span class="dim">({{ c.article }})</span>
      <span class="badge badge-{{ c.status.value }}">{{ c.status.value | replace('_', ' ') }}</span>
      <span class="ev ev-{{ c.evidenceability.value }}">{{ c.evidenceability.value }}</span>
    </h3>
    {% if c.evidence %}
    <ul class="evidence">
      {% for e in c.evidence %}<li>{{ e }}</li>{% endfor %}
    </ul>
    {% endif %}
    {% if c.gap %}<p class="gap"><strong>Gap:</strong> {{ c.gap }}</p>{% endif %}
    {% if c.remediation %}<p class="rem"><strong>Remediation:</strong> {{ c.remediation }}</p>{% endif %}
  </article>
  {% endfor %}
</section>

<section class="not-evidenceable">
  <h2>Not trace-evidenceable</h2>
  <p class="dim">These Article 12 sub-requirements need artifacts outside trace data:</p>
  <ul>
  {% for n in not_evidenceable %}
    <li><strong>{{ n.article }} — {{ n.name }}</strong>: {{ n.needs }}</li>
  {% endfor %}
  </ul>
</section>

<footer>
  <p>AgentAudit v{{ version }} · {{ rep.checks | length }} trace-evidenceable checks ·
    Source: OpenTelemetry GenAI semantic conventions · Not legal advice.</p>
</footer>
</div>
</body>
</html>
"""


def generate_html(rep: Report) -> str:
    """Render a Report into a single self-contained HTML string."""
    env = jinja2.Environment(autoescape=True)
    tmpl = env.from_string(_TEMPLATE)
    counts = _status_counts(rep)
    not_evidenceable: list[dict[str, Any]] = RULES.get("not_trace_evidenceable", [])
    return tmpl.render(
        rep=rep,
        css=_CSS,
        version=__version__,
        counts=counts,
        not_evidenceable=not_evidenceable,
    )


def _status_counts(rep: Report) -> dict[str, int]:
    counts = {s.value: 0 for s in CheckStatus}
    for c in rep.checks:
        counts[c.status.value] += 1
    return counts

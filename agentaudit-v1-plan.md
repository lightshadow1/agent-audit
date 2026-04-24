# AgentAudit v1 — Narrow Build Plan

**Scope:** Ship an open-source CLI that turns OpenTelemetry GenAI traces into an EU AI Act Article 12 evidence report. One framework. One input format (primary). One output format. Honest about what traces can and cannot prove.

**Timeline:** 4 focused days, single agent build (or one developer). Not a 5-agent team.

---

## 1. Positioning

> "OpenTelemetry GenAI → EU AI Act Article 12 evidence mapper. We tell you what your traces prove, and what they don't."

The differentiator is not coverage (every tool claims coverage). It is **honesty about trace evidenceability**. Article 12 has sub-requirements (risk management system docs, technical documentation, quality management records) that no tracing tool can evidence. v1 names that boundary and audits only what sits inside it.

## 2. In / Out

**In scope (v1):**
- Input: OpenTelemetry GenAI semantic-convention JSONL (primary)
- Input: Langfuse REST (secondary, convenience adapter)
- Assessment: EU AI Act Article 12, 7 trace-evidenceable checks
- Output: Single-file HTML report
- CLI: `agentaudit report <input> --out report.html`

**Out of scope (defer to v2+):**
- PDF generation (use browser print-to-PDF)
- SOC 2, NIST AI RMF, ISO 42001, Colorado AI Act, OMB M-26-04
- Harness architecture assessment (generator/evaluator, sprint contracts) — novel, but research scope, no vendor emits these events today
- AI system inventory, training data governance (not derivable from traces)
- Synthetic demo trace generator (use real traces from a toy agent instead)
- SaaS, auth, dashboards, real-time monitoring

## 3. Repo layout

```
agentaudit/
├── pyproject.toml
├── README.md
├── LICENSE                        # Apache 2.0
├── src/agentaudit/
│   ├── __init__.py                # __version__ = "0.1.0"
│   ├── cli.py                     # typer: report, version
│   ├── models.py                  # Pydantic, OTel-aligned — PIN FIRST
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── otel.py                # Primary
│   │   └── langfuse.py            # Secondary
│   ├── article12.py               # 7 checks
│   ├── rules/article12.yaml
│   └── report.py                  # Jinja2 HTML, inline CSS
├── tests/
│   ├── fixtures/
│   │   ├── otel_pass.jsonl        # Real spans, passes all checks
│   │   └── otel_fail.jsonl        # Real spans, fails specific checks
│   ├── test_otel_adapter.py
│   ├── test_article12.py
│   └── test_report.py
└── examples/
    └── toy_agent.py               # Emits fixtures/otel_pass.jsonl
```

## 4. Data model (commit this before anything else)

This is the contract that prevented schema-drift problems in the v5 prompt. Write it verbatim on Day 1, commit, then build against it.

```python
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class SpanKind(str, Enum):
    llm = "llm"              # gen_ai.* span
    tool = "tool"            # gen_ai.tool / function call
    agent = "agent"          # internal orchestration node
    oversight = "oversight"  # explicit human-in-the-loop marker

class Span(BaseModel):
    """Normalized OpenTelemetry GenAI span."""
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    kind: SpanKind
    name: str
    start_time: datetime                        # UTC, tz-aware
    end_time: datetime                          # UTC, tz-aware
    model: str | None = None                    # gen_ai.request.model
    input_tokens: int | None = None             # gen_ai.usage.input_tokens
    output_tokens: int | None = None            # gen_ai.usage.output_tokens
    prompt: str | None = None                   # gen_ai.prompt (may be redacted)
    completion: str | None = None               # gen_ai.completion
    error_type: str | None = None               # exception.type
    error_message: str | None = None            # exception.message
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)

class Trace(BaseModel):
    trace_id: str
    spans: list[Span]

class Evidenceability(str, Enum):
    fully = "fully"                   # traces can prove this
    partially = "partially"           # traces + user-declared config
    not_from_traces = "not-from-traces"  # needs other artifacts

class CheckStatus(str, Enum):
    met = "met"
    partial = "partial"
    not_met = "not_met"
    not_evidenced = "not_evidenced"   # trace doesn't even speak to this

class CheckResult(BaseModel):
    check_id: str
    article: str                      # e.g. "Art. 12(1)"
    name: str
    evidenceability: Evidenceability
    status: CheckStatus
    evidence: list[str] = Field(default_factory=list, max_length=5)
    gap: str | None = None
    remediation: str | None = None

class Report(BaseModel):
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    traces_analyzed: int
    spans_analyzed: int
    checks: list[CheckResult]
```

## 5. The 7 Article 12 checks

Correcting a drift in the v5 prompt: serious-incident reporting is **Art. 73**, not Art. 79 (Art. 79 is confidentiality).

| check_id | Article | What traces prove | Evidenceability |
|---|---|---|---|
| `auto_logging` | 12(1) | ≥95% of agent invocations produce ≥1 span | fully |
| `session_timestamps` | 12(3)(a) | All spans have tz-aware UTC start+end, monotonic within trace, no gaps >60s | fully |
| `input_recording` | 12(3)(c) | `prompt` field present on ≥80% of `kind=llm` spans | fully |
| `operational_monitoring` | 12(2)(c) | Latency + token usage + error fields populated | fully |
| `human_oversight_marker` | 14 | Count explicit `kind=oversight` spans; do not infer from other events | partially |
| `log_retention` | 26(6) | Retention policy ≥ 180 days (user flag: `--retention-days`) | partially |
| `incident_reporting` | 73 | Error spans carry `error_type` + structured severity | partially |

Everything else in Article 12 (risk management system 12(2)(a), post-market monitoring 12(2)(b), EN 18229-1 component identification, etc.) is reported as `not_from_traces` with a one-line explanation in the report's "Not trace-evidenceable" section. That's the honesty move.

Thresholds live in `rules/article12.yaml`; don't hardcode them in the check functions.

## 6. Report structure (HTML, single file)

1. **Header** — tool version, `generated_at`, assessment period
2. **Honesty notice** (prominent, top of body):
   > This report evaluates EU AI Act Article 12 evidence *derivable from OpenTelemetry traces alone*. {X} of 7 trace-evidenceable checks passed. Article 12 contains sub-requirements that no tracing tool can evidence (risk management documentation, quality management system records, technical documentation) — these require separate artifacts. This is not legal advice and does not certify compliance.
3. **Summary table** — 7 checks, status badge, evidenceability column
4. **Per-check detail** — evidence snippets (span_id + first 200 chars of prompt/completion), gap line, remediation line
5. **Not trace-evidenceable** — the Article 12 sub-requirements that need other sources, with one-line pointers to what artifact would evidence each
6. **Methodology footer** — checks run, thresholds used, assumptions, disclaimer

No urgency banners. No market stats ($2.55B, 78%, etc. — those date the report). No competitor comparisons. No hardcoded deadline countdowns. Keep the report auditor-credible, not marketing-credible.

## 7. Day-by-day execution

### Day 1 — models + OTel adapter
- Write `models.py` exactly as spec'd in §4. Commit.
- Write `examples/toy_agent.py`: ~30-line agent (any framework, or just direct Anthropic SDK) that emits OTel spans to `tests/fixtures/otel_pass.jsonl`. Use `opentelemetry-sdk` + the OTLP file exporter.
- Write `adapters/otel.py`: read JSONL, map GenAI semantic conventions → `Span` / `Trace`.
- Write `tests/test_otel_adapter.py` against the real fixture.
- **Exit:** `pytest tests/test_otel_adapter.py` green; `load("tests/fixtures/otel_pass.jsonl")` returns non-empty `list[Trace]`.

### Day 2 — Article 12 checks
- Write `rules/article12.yaml` with the 7 checks and their thresholds.
- Write `article12.py`: one function per check, each returns `CheckResult`. Plus a top-level `assess(traces, retention_days) -> list[CheckResult]`.
- Hand-author `tests/fixtures/otel_fail.jsonl` by mutating the pass fixture (strip timestamps, drop prompts, remove oversight spans).
- Write `tests/test_article12.py`: for each check, one passing fixture and one failing fixture.
- **Exit:** `pytest tests/test_article12.py -v` green, ≥2 tests per check.

### Day 3 — HTML report + CLI
- Write `report.py`: Jinja2 template as a Python string constant, inline CSS, single-file output. Light mode only.
- Write `cli.py`: `agentaudit report <input.jsonl> --out report.html --retention-days 180 --source otel|langfuse`.
- If time permits: `adapters/langfuse.py`.
- Write `tests/test_report.py`: generate report from fixture, assert key section strings present, assert valid HTML.
- **Exit:** `agentaudit report tests/fixtures/otel_pass.jsonl --out /tmp/r.html` opens in a browser and shows all 7 checks passing; `otel_fail.jsonl` shows a realistic mix of gaps.

### Day 4 — polish + launch
- Write `README.md`: quick-start, honest-scope paragraph, one worked example, link to Article 12 text.
- Add `LICENSE` (Apache 2.0).
- `pip install build twine && python -m build` — publish to TestPyPI first, then PyPI. Check name availability; `otel-aiact` is a fallback.
- Post once to one community channel (OpenTelemetry GitHub Discussions, CNCF #otel-genai Slack, r/LocalLLaMA governance thread — pick one, don't spam).
- **Exit:** a stranger can `pip install agentaudit`, run against their own OTel JSONL, and get a report in <5 min.

## 8. Honesty contract (verbatim — README top, report top, `--help`)

> AgentAudit evaluates EU AI Act Article 12 evidence that is derivable from OpenTelemetry GenAI traces. Article 12 contains sub-requirements (risk management system documentation, quality management records, technical documentation, component identification under EN 18229-1) that no tracing tool can evidence — those require separate artifacts. This report is not legal advice and does not certify compliance. It provides auditable evidence for the subset of Article 12 that trace data can demonstrate, and explicitly names the subset it cannot.

## 9. Success criteria (realistic)

- v0.1.0 published on PyPI within 1 week of starting
- End-to-end works on one real (non-toy) OTel trace export supplied by someone else
- 20 stars in 2 weeks from a single community post (not 200 — that was the v5 spec's optimism)
- One unsolicited issue or PR from an external user within 30 days = product-market pull signal

## 10. Explicit non-goals (v2+ only)

Defer these until v1 has real users and you have signal on what they actually need:

- Harness architecture assessment (topology detection, sprint contracts, evaluator calibration)
- Additional frameworks — add SOC 2 CC mappings first (same trace evidence, different labels), then NIST AI RMF
- AI system inventory, training data governance
- PDF export
- Real-time monitoring, alerting
- GRC tool integrations (ServiceNow, Archer)
- Dashboard / web UI

## 11. Build environment note

This directory (`/Users/williamsuriaputra/dev/agent-audit/`) already contains the MVP spec, v5 prompt, and demo artifacts. Create the v1 project in a subdirectory (`./agentaudit/`) or sibling directory to avoid commingling spec and build output.

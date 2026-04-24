# AgentAudit — MVP Technical Specification

**Version:** 3.0
**Date:** March 31, 2026
**Author:** Will
**Status:** Draft — solo build with AI coding tools

---

## 1. Overview

### What Changed (v2 → v3)

The agent observability space got crowded fast. Laminar ($3M seed, YC S24, 2.7K stars), Opik (18.5K stars), Langfuse (20K stars, ClickHouse-backed), Helicone, AgentOps, and AgentLens all provide open-source, self-hostable tracing SDKs with dashboards. Building another tracing SDK is a losing battle.

But **none of them do compliance**. Zero mention of EU AI Act, Article 12, SOC 2 mapping, or audit-grade reporting in any of their repos. That's our gap.

### What We're Building Now

A **compliance bridge** that sits on top of existing agent observability tools. It ingests trace data from any source (Langfuse, Laminar, Opik, Helicone, AgentOps, raw OTel) and produces regulatory-grade compliance reports.

**One-liner:** "Turn your agent traces into EU AI Act + SOC 2 compliance evidence."

We don't compete on tracing. We don't compete on dashboards. We compete on **compliance interpretation** — mapping raw observability data to specific regulatory requirements and telling you exactly what's compliant, what's missing, and how to fix the gaps.

### What We're NOT Building (v1)

- No tracing SDK (use Langfuse/Laminar/Opik — they're better at it)
- No trace visualization dashboard (they all have one)
- No cloud/SaaS (local CLI + web report viewer)
- No real-time monitoring or alerting
- No user accounts, auth, billing, team features

### Success Criteria

The MVP is successful if:

1. A user can point AgentAudit at their existing Langfuse/Laminar/OTel traces and get a compliance report in <5 minutes
2. The report clearly maps trace evidence to Article 12 requirements AND SOC 2 CC criteria
3. Gap analysis identifies specific missing evidence with actionable fix recommendations
4. At least 200 GitHub stars and meaningful engagement from compliance/governance community in first 2 weeks

---

## 2. Target Users

**Primary:** Engineering leads and AI platform teams at companies that already use an observability tool (Langfuse, Laminar, etc.) and need to demonstrate compliance for EU AI Act or SOC 2 audits.

**Secondary:** Compliance officers, AI governance leads, and auditors at regulated companies (finance, healthcare, government) who need to verify and report on AI agent behavior.

**Anti-target:** Developers looking for a tracing/debugging tool. Send them to Langfuse or Laminar.

---

## 3. Architecture

### High-Level Flow

```
┌──────────────────────────────────────────────────┐
│  Existing Observability Data                      │
│                                                   │
│  Langfuse traces  ─┐                              │
│  Laminar traces   ─┤                              │
│  Opik traces      ─┼── Import Adapters ──┐        │
│  OTel JSONL/OTLP  ─┤                    │        │
│  Raw JSONL files  ─┘                    ▼        │
│                                                   │
│              ┌────────────────────────┐            │
│              │  Normalizer            │            │
│              │  Raw traces → unified  │            │
│              │  AgentAudit schema     │            │
│              └──────────┬─────────────┘            │
│                         │                          │
│                         ▼                          │
│              ┌────────────────────────┐            │
│              │  Compliance Engine     │            │
│              │                        │            │
│              │  ┌──────────────────┐  │            │
│              │  │ Article 12       │  │            │
│              │  │ Mapper           │  │            │
│              │  └──────────────────┘  │            │
│              │  ┌──────────────────┐  │            │
│              │  │ SOC 2 CC         │  │            │
│              │  │ Mapper           │  │            │
│              │  └──────────────────┘  │            │
│              │  ┌──────────────────┐  │            │
│              │  │ Gap Analyzer     │  │            │
│              │  └──────────────────┘  │            │
│              │  ┌──────────────────┐  │            │
│              │  │ Hash Chain       │  │            │
│              │  │ Verifier/Wrapper │  │            │
│              │  └──────────────────┘  │            │
│              └──────────┬─────────────┘            │
│                         │                          │
│                         ▼                          │
│              ┌────────────────────────┐            │
│              │  Report Generator      │            │
│              │                        │            │
│              │  • PDF (auditor-ready)  │            │
│              │  • JSON (machine)       │            │
│              │  • HTML (viewable)      │            │
│              │  • CSV (GRC import)     │            │
│              └────────────────────────┘            │
└──────────────────────────────────────────────────┘
```

### Tech Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Language | Python 3.10+ | Matches observability ecosystem |
| CLI framework | Click or Typer | Standard Python CLI |
| Import adapters | httpx + provider-specific SDKs | Fetch traces from APIs |
| Normalized schema | Pydantic models | Strict typing, validation |
| Compliance rules | Python rule engine (custom) | Auditable, testable logic |
| Hash verification | hashlib (SHA-256) | Verify existing chains or add wrapper |
| Report: PDF | fpdf2 | Lightweight, no heavy deps |
| Report: HTML | Jinja2 templates | Rich interactive reports |
| Report: JSON/CSV | stdlib | No deps needed |
| Package | PyPI | Standard distribution |

---

## 4. Import Adapters

### 4.1 Supported Sources (v1 — pick top 3 by adoption)

**Tier 1 (must-have for launch):**

| Source | How to Import | Data Available |
|--------|--------------|---------------|
| **Langfuse** | REST API (`/api/public/traces`, `/api/public/observations`) | Traces, spans, LLM calls, scores, metadata |
| **OTel JSONL / OTLP export** | Read local files or connect to OTLP endpoint | Spans with gen_ai.* semantic conventions |
| **Raw JSONL** | Read local files in AgentAudit's own schema | Direct — useful for teams with custom logging |

**Tier 2 (post-launch, based on demand signals):**

| Source | How to Import |
|--------|--------------|
| Laminar | REST API or exported traces |
| Opik | REST API (`/api/v1/traces`) |
| Helicone | REST API |
| LangSmith | API (if publicly accessible) |

### 4.2 Adapter Interface

Each adapter implements a simple interface:

```python
class TraceAdapter(Protocol):
    def fetch_traces(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 1000,
    ) -> list[NormalizedTrace]:
        """Fetch traces from the source and normalize them."""
        ...

    def test_connection(self) -> bool:
        """Verify credentials and connectivity."""
        ...
```

### 4.3 Normalized Schema (Internal)

All traces are converted to a unified format before compliance analysis:

```python
class NormalizedEvent:
    event_id: str
    trace_id: str
    timestamp: datetime
    event_type: EventType  # node_execution | llm_call | tool_call | branch | human_oversight | error | state_mutation
    node_name: str | None
    parent_event_id: str | None
    input_data: dict | None        # What went in (truncated)
    output_data: dict | None       # What came out (truncated)
    duration_ms: float | None
    metadata: dict                 # Flexible: model name, tokens, cost, tool name, branch condition, error info, etc.
    source: str                    # "langfuse" | "otel" | "laminar" | "raw"
    raw_event: dict                # Original event preserved for auditors

class NormalizedTrace:
    trace_id: str
    agent_name: str
    timestamp_start: datetime
    timestamp_end: datetime | None
    status: str                    # completed | failed | running
    events: list[NormalizedEvent]
    total_llm_calls: int
    total_tool_calls: int
    total_tokens: int
    estimated_cost_usd: float
    has_human_oversight: bool
    has_hash_chain: bool
    hash_chain_valid: bool | None
```

---

## 5. Compliance Engine

### 5.1 EU AI Act Article 12 Mapper

Maps normalized trace data against every Article 12 requirement and connected articles:

```python
class Article12Assessment:
    # Core Article 12 requirements
    automatic_logging: ComplianceStatus        # Art. 12(1): system generates logs automatically
    risk_event_recording: ComplianceStatus      # Art. 12(2)(a): events relevant to risk identification
    post_market_monitoring: ComplianceStatus    # Art. 12(2)(b): supports Art. 72 surveillance
    operational_monitoring: ComplianceStatus    # Art. 12(2)(c): deployer can monitor operations (Art. 26(5))

    # Connected article requirements
    human_oversight_logging: ComplianceStatus   # Art. 14: human intervention points logged
    transparency_documentation: ComplianceStatus # Art. 13: users informed about logging
    log_retention: ComplianceStatus             # Art. 26: minimum 6 months retention
    incident_capability: ComplianceStatus       # Art. 72/79: supports incident reporting (72-hour window)
    tamper_evidence: ComplianceStatus           # EN 18229-1: log integrity verifiable

    # Derived from EN 18229-1 / ISO 24970:2025 draft standards
    error_event_capture: ComplianceStatus       # Error codes, severity, context
    component_identification: ComplianceStatus  # Which system component produced each event
    timestamp_completeness: ComplianceStatus    # Every event has a timestamp
    data_flow_traceability: ComplianceStatus    # Inputs traceable through to outputs

class ComplianceStatus:
    status: Literal["met", "partial", "not_met", "not_applicable"]
    confidence: float                           # 0.0 to 1.0
    evidence_count: int                         # Number of trace events supporting this
    evidence_sample: list[str]                  # Sample event IDs as evidence
    gap_description: str | None                 # What's missing (if partial or not_met)
    remediation: str | None                     # How to fix it
```

**Assessment logic (examples):**

| Requirement | "Met" Condition | "Partial" Condition | "Not Met" Condition |
|-------------|----------------|--------------------|--------------------|
| Automatic logging | >95% of traces have system-generated events (not manual) | 50-95% coverage | <50% or no evidence of automatic generation |
| Risk event recording | Error events, anomaly markers, or risk-flagged events present | Some error events but no risk classification | No error events captured |
| Human oversight logging | human_oversight events present in >80% of traces that involve high-risk decisions | Some human events but inconsistent | No human_oversight events in any trace |
| Tamper evidence | Hash chain present and verified intact | Hash chain present but broken at some points | No hash chain or integrity mechanism |
| Log retention | Traces span at least 6 months of history | 3-6 months available | <3 months of trace data |
| Component identification | Every event has a node_name or component identifier | >70% of events have identifiers | Insufficient identification |

### 5.2 SOC 2 CC Mapper

Maps the same normalized traces against relevant SOC 2 Common Criteria:

```python
class SOC2Assessment:
    # CC criteria relevant to AI agent observability
    cc7_1: ComplianceStatus   # Detect and monitor for anomalies — are anomalies/errors logged?
    cc7_2: ComplianceStatus   # Monitor for malicious acts, failures, errors — are these captured?
    cc7_3: ComplianceStatus   # Evaluate detected events — is there triage/severity?
    cc7_4: ComplianceStatus   # Respond to incidents — is incident context sufficient?
    cc7_5: ComplianceStatus   # Root cause analysis — are traces detailed enough for RCA?

    cc6_1: ComplianceStatus   # Logical access controls — is access to agent systems logged?
    cc6_6: ComplianceStatus   # System component access — API keys, service accounts tracked?

    cc8_1: ComplianceStatus   # Change management — are agent/model version changes logged?

    cc5_1: ComplianceStatus   # Control activities — are security controls evidenced in traces?
    cc5_3: ComplianceStatus   # Policies in action — are human oversight policies executed?

    cc3_2: ComplianceStatus   # Risk identification — do traces support risk assessment?

    cc2_3: ComplianceStatus   # Third-party communication — are external API calls logged?

    # Additional criteria (if selected by user)
    pi1_2: ComplianceStatus   # Processing integrity — do outputs match specifications?
    pi1_3: ComplianceStatus   # Input completeness — are all inputs recorded?
    pi1_4: ComplianceStatus   # Output completeness — are all outputs recorded?

    a1_1: ComplianceStatus    # Availability monitoring — is uptime/capacity tracked?

    c1_1: ComplianceStatus    # Confidentiality — is sensitive data identified and handled?

    p1_1: ComplianceStatus    # Privacy notice — is PII handling documented?
```

### 5.3 Gap Analyzer

Compares Article 12 + SOC 2 assessments and produces:

```python
class GapAnalysis:
    overall_article12_score: float        # 0-100%
    overall_soc2_score: float             # 0-100% (for selected criteria)
    critical_gaps: list[Gap]              # Must fix — blocks compliance
    warnings: list[Gap]                   # Should fix — weakens compliance posture
    passing: list[PassingRequirement]     # Evidence exists and is sufficient

class Gap:
    framework: str                        # "article_12" | "soc2"
    requirement_id: str                   # e.g., "art12_human_oversight" or "cc7_3"
    requirement_name: str                 # Human-readable name
    severity: Literal["critical", "warning"]
    current_state: str                    # What the traces currently show
    required_state: str                   # What compliance demands
    remediation_steps: list[str]          # Specific actions to fix
    affected_traces: int                  # How many traces are impacted
    observability_tool_action: str | None # "Add human_in_loop callback in Langfuse" etc.
```

**Example gap output:**

```
CRITICAL GAP: Human Oversight Logging (Article 14 + CC5.3)

Current state: 0 out of 347 traces contain human_oversight events.
Required state: Article 14 requires logging of human intervention points
  for high-risk AI systems. SOC 2 CC5.3 requires deployment of controls
  through policies and procedures.

Remediation:
  1. Add human-in-the-loop checkpoints in your LangGraph graph using
     interrupt_before/interrupt_after
  2. Configure your observability tool to capture these events:
     - Langfuse: Use trace.event(name="human_oversight", ...)
     - Laminar: Add @observe decorator on approval functions
     - OTel: Create spans with gen_ai.human_oversight attribute
  3. Re-run assessment after 30 days of data collection

Affected traces: 347 of 347 (100%)
```

---

## 6. Report Generator

### 6.1 Report Types

**PDF Report (Primary — for auditors and regulators)**

Structure:
1. Cover page: Organization name, assessment period, report date, frameworks assessed
2. Executive summary: Overall compliance scores, critical gap count, key findings (1 page)
3. Article 12 detailed assessment: Each requirement with status, evidence, gaps
4. SOC 2 CC detailed assessment: Each criterion with status, evidence, gaps
5. Cross-framework overlap analysis: Requirements satisfied by both frameworks simultaneously
6. Gap analysis and remediation plan: Prioritized list of gaps with fix instructions
7. Evidence appendix: Sample trace data supporting each "met" requirement
8. Methodology: How the assessment was performed, data sources, confidence levels

**HTML Report (for internal review)**
- Same content as PDF but interactive
- Collapsible sections, clickable evidence links, search
- Can be opened locally in any browser

**JSON Report (machine-readable)**
- Full assessment data in structured JSON
- Importable by GRC tools (Vanta, Drata, Secureframe, OneTrust)
- Designed for CI/CD integration

**CSV Export (for spreadsheets)**
- Requirements checklist with status columns
- Easy to share with non-technical stakeholders

### 6.2 Report Branding

- Clean, professional, minimal
- No AgentAudit branding on the report itself (the auditor doesn't need to see your tool name)
- Organization name and logo configurable via CLI flags
- Page numbers, table of contents, proper pagination

---

## 7. CLI Interface

### 7.1 Commands

```bash
# Setup & configuration
agentaudit init                                    # Interactive setup — pick your observability source, set credentials
agentaudit config show                             # Show current config
agentaudit config set source langfuse              # Change config values
agentaudit test-connection                         # Verify connectivity to trace source

# Import & assess
agentaudit import --source langfuse --days 90      # Import traces from last 90 days
agentaudit import --source otel --path ./traces/   # Import from local OTel files
agentaudit import --source raw --path ./my-logs/   # Import raw JSONL files

agentaudit assess                                  # Run compliance assessment on imported data
agentaudit assess --framework article12            # Assess only Article 12
agentaudit assess --framework soc2                 # Assess only SOC 2
agentaudit assess --framework all                  # Both (default)

# Reports
agentaudit report --format pdf --output report.pdf # Generate PDF report
agentaudit report --format html --output report.html
agentaudit report --format json --output report.json
agentaudit report --format csv --output report.csv

# Utilities
agentaudit gaps                                    # Print gap analysis to terminal (quick view)
agentaudit score                                   # Print compliance scores to terminal
agentaudit verify                                  # Verify hash chain integrity on imported traces
agentaudit version
```

### 7.2 Interactive Init Flow

```
$ agentaudit init

Welcome to AgentAudit — AI compliance assessment tool.

Where are your agent traces stored?
  [1] Langfuse (cloud or self-hosted)
  [2] Laminar
  [3] OpenTelemetry files (JSONL/OTLP)
  [4] Raw JSONL files
  > 1

Langfuse configuration:
  Base URL [https://cloud.langfuse.com]: https://cloud.langfuse.com
  Public Key: pk-lf-xxx
  Secret Key: sk-lf-xxx

Testing connection... ✓ Connected. Found 347 traces.

Which compliance frameworks do you need?
  [1] EU AI Act (Article 12 + connected articles)
  [2] SOC 2 (Common Criteria)
  [3] Both
  > 3

Configuration saved to ~/.agentaudit/config.yaml
Run 'agentaudit import --days 90' to pull your traces.
```

---

## 8. Scope Boundaries

### Explicitly Out of Scope for v1

| Feature | Why Not Now |
|---------|------------|
| Own tracing SDK | Langfuse/Laminar/Opik already do this. Don't reinvent |
| Trace visualization / dashboard | They all have dashboards. Our value is compliance, not debugging |
| Real-time monitoring | Compliance is periodic assessment, not real-time |
| Cloud/SaaS version | Validate locally first |
| CI/CD integration | v2 feature — `agentaudit assess --fail-on critical` in GitHub Actions |
| Auto-remediation | v2 — automatically adding missing events to agent code |
| Multi-tenant / team features | Only if cloud signals emerge |
| HIPAA / PCI-DSS mapping | v2 — add more frameworks after Article 12 + SOC 2 are solid |

### Nice-to-Haves (If Time Allows)

| Feature | Value |
|---------|-------|
| `agentaudit watch --source langfuse --interval 7d` | Auto-reassess weekly |
| Trend tracking | "Your Article 12 score improved from 62% to 78% this month" |
| Remediation code snippets | "Add this callback to your LangGraph agent to capture human oversight" |
| GRC tool export templates | Pre-formatted for Vanta, Drata, Secureframe |

---

## 9. Deliverables & Milestones (Solo Build — 2 Week Sprint)

### Build Approach

Solo founder with AI coding tools. This product is significantly leaner than v2 — no SDK, no dashboard, no OTel instrumentation from scratch. The core is: adapters + compliance rules + report templates.

### Sprint Plan

#### Week 1: Core Engine (Days 1-5)

**Day 1: Scaffolding + Normalized Schema**
- Repo structure, pyproject.toml, dev environment
- Pydantic models for NormalizedTrace, NormalizedEvent
- Config system with YAML persistence

**Day 2-3: Import Adapters**
- Langfuse adapter (REST API — fetch traces, observations, scores)
- OTel JSONL adapter (read local files with gen_ai.* conventions)
- Raw JSONL adapter (simple file reader)
- Normalizer that converts source-specific formats → unified schema
- Test each adapter with real data (stand up a free Langfuse cloud account)

**Day 4: Compliance Engine**
- Article 12 mapper with all assessment rules
- SOC 2 CC mapper (CC7.x, CC6.x, CC5.x, CC3.x, PI1.x focus)
- Gap analyzer with severity classification and remediation text
- Hash chain verifier (check existing chains or flag absence)

**Day 5: Tests**
- Unit tests for each adapter with mock API responses
- Unit tests for compliance rules (known-good traces → expected scores)
- Unit tests for gap analyzer (traces with deliberate gaps → correct gap identification)
- Integration test: mock Langfuse data → import → assess → verify scores

**Checkpoint:** `agentaudit import --source raw --path ./test-traces/ && agentaudit assess` produces correct compliance scores on test data.

#### Week 2: Reports + CLI + Launch (Days 6-10)

**Day 6-7: Report Generator**
- PDF report with fpdf2 (cover page, executive summary, detailed assessment, gap analysis, evidence appendix)
- HTML report with Jinja2 (interactive, collapsible sections)
- JSON report (structured, GRC-importable)
- CSV export (requirements checklist)
- Test: generate all 4 report types, review manually for accuracy and readability

**Day 8: CLI Polish**
- `agentaudit init` interactive setup flow
- All CLI commands from Section 7.1
- Colored terminal output for `gaps` and `score` commands
- Error handling with helpful messages

**Day 9: README + Examples + Packaging**
- README with clear value proposition, quickstart, sample output
- Example: assess sample Langfuse traces and show the gap analysis
- PyPI packaging and test publish

**Day 10: Launch**
- Publish to PyPI
- Push to GitHub (MIT license)
- Write and post Show HN
- Share in compliance/governance communities

**Target launch date: ~April 14, 2026** (3.5 months before EU AI Act deadline)

---

## 10. AI Coding Tool Strategy

### Where AI Tools Excel for This Project

- Pydantic model generation (well-defined schemas)
- REST API client code for Langfuse/Laminar adapters
- PDF generation with fpdf2 (lots of training data)
- Jinja2 HTML templates
- CLI scaffolding with Click/Typer
- pytest fixtures with mock API responses

### Where You Must Apply Your Own Judgment

- **Compliance rule logic** — The mapping of trace events to Article 12 / SOC 2 requirements is the core IP. Don't let the AI guess what "met" means. Define the rules yourself based on the legal text.
- **Gap remediation text** — This must be accurate, specific, and actionable. A wrong remediation recommendation undermines trust in the entire tool.
- **Report layout and tone** — Must read like a professional compliance report, not a developer dashboard. Review every generated report manually.
- **README and Show HN post** — Write these yourself. Your authentic understanding of the compliance gap is what resonates.

### Anti-Patterns to Avoid

1. **Don't let the AI invent compliance requirements.** Every rule must trace back to a specific article, paragraph, or CC code. If you can't cite it, don't assess it.
2. **Don't over-build the adapters.** The Langfuse API is well-documented. Import traces, normalize, move on. Don't build a full Langfuse client library.
3. **Don't make the reports pretty before they're accurate.** Content correctness first, formatting second.

---

## 11. Repository Structure

```
agentaudit/
├── pyproject.toml
├── README.md
├── LICENSE (MIT)
├── CONTRIBUTING.md
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── release.yml
├── src/
│   └── agentaudit/
│       ├── __init__.py
│       ├── cli.py                    # CLI entry point
│       ├── config.py                 # Config management (YAML-based)
│       ├── models.py                 # NormalizedTrace, NormalizedEvent, ComplianceStatus, etc.
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── base.py               # TraceAdapter protocol
│       │   ├── langfuse.py           # Langfuse REST API adapter
│       │   ├── otel.py               # OTel JSONL/OTLP adapter
│       │   └── raw.py                # Raw JSONL file adapter
│       ├── compliance/
│       │   ├── __init__.py
│       │   ├── article12.py          # Article 12 assessment rules
│       │   ├── soc2.py               # SOC 2 CC assessment rules
│       │   ├── gaps.py               # Gap analyzer + remediation engine
│       │   └── hashchain.py          # Hash chain verifier
│       ├── reports/
│       │   ├── __init__.py
│       │   ├── pdf.py                # PDF report generator
│       │   ├── html.py               # HTML report generator
│       │   ├── json_report.py        # JSON report generator
│       │   ├── csv_report.py         # CSV export
│       │   └── templates/
│       │       └── report.html.j2    # Jinja2 HTML template
│       └── utils.py                  # Shared utilities
├── tests/
│   ├── conftest.py                   # Fixtures, mock traces
│   ├── test_adapters/
│   │   ├── test_langfuse.py
│   │   ├── test_otel.py
│   │   └── test_raw.py
│   ├── test_compliance/
│   │   ├── test_article12.py
│   │   ├── test_soc2.py
│   │   ├── test_gaps.py
│   │   └── test_hashchain.py
│   ├── test_reports/
│   │   └── test_pdf.py
│   ├── test_cli.py
│   └── test_integration.py
├── examples/
│   ├── sample_traces/                # Sample JSONL traces for testing
│   └── sample_report.pdf             # Example output report
└── compliance_rules/
    ├── article12.yaml                # Article 12 rules in structured format
    └── soc2.yaml                     # SOC 2 CC rules in structured format
```

---

## 12. Compliance Rules Format

Rules are defined in YAML for transparency and auditability (auditors can inspect the rules):

```yaml
# compliance_rules/article12.yaml
framework: eu_ai_act
version: "2024/1689"

requirements:
  - id: art12_automatic_logging
    article: "12(1)"
    name: "Automatic Recording of Events"
    description: "High-risk AI systems shall technically allow for the automatic recording of events (logs) over the lifetime of the system."
    severity: critical
    assessment:
      type: event_coverage
      condition: "percentage of traces with system-generated events > 95%"
      event_types_required: ["node_execution", "llm_call", "tool_call"]
      met_threshold: 0.95
      partial_threshold: 0.50
    remediation:
      short: "Ensure your observability tool captures all agent events automatically"
      detailed: |
        Your agent traces must be generated by the system itself, not manually created.
        Most observability tools (Langfuse, Laminar, Opik) do this by default when
        properly instrumented. Verify that:
        1. Every agent execution produces a trace
        2. Traces contain node_execution, llm_call, and tool_call events
        3. No manual intervention is needed to generate traces

  - id: art12_risk_identification
    article: "12(2)(a)"
    name: "Risk Event Recording"
    description: "Logging capabilities shall enable the recording of events relevant for identifying situations that may result in risk."
    severity: critical
    assessment:
      type: event_presence
      condition: "error events and anomaly markers present in traces"
      event_types_required: ["error"]
      met_threshold: 0.80
      partial_threshold: 0.30
    remediation:
      short: "Ensure errors, exceptions, and anomalies are captured in traces"
      detailed: |
        Article 12(2)(a) requires that your logs can identify risk situations.
        At minimum, your traces must capture:
        - All exceptions and errors with full context
        - Anomalous behavior (unexpected tool calls, excessive token usage)
        - Model confidence scores or quality metrics when available

  - id: art14_human_oversight
    article: "14"
    name: "Human Oversight Logging"
    description: "Logging of human intervention and oversight points."
    severity: critical
    assessment:
      type: event_presence
      condition: "human_oversight events present in traces involving high-risk decisions"
      event_types_required: ["human_oversight"]
      met_threshold: 0.80
      partial_threshold: 0.10
    remediation:
      short: "Add human-in-the-loop checkpoints and log them"
      langfuse: "Use trace.event(name='human_oversight', metadata={...})"
      laminar: "Add @observe decorator on approval/review functions"
      langgraph: "Use interrupt_before/interrupt_after on critical nodes"

  # ... additional requirements ...
```

---

## 13. Budget Breakdown

| Item | Cost | Notes |
|------|------|-------|
| AI coding tool | $20/month | Already have it |
| Langfuse cloud (free tier) | $0 | For testing the adapter |
| Domain | $10-50 | agentaudit.dev or similar |
| PyPI | $0 | Free |
| GitHub | $0 | Free for public repos |
| **Total** | **$30-70** | |

---

## 14. Post-MVP Signals

Upgrade to cloud/paid ONLY if you see 2+ of these within 8 weeks:

| Signal | Measurement |
|--------|-------------|
| "Can I run this in CI/CD?" | GitHub issues requesting pipeline integration |
| "Can I schedule recurring assessments?" | Demand for automated periodic compliance checks |
| "Can we share reports with our auditor?" | Multi-user/sharing requests |
| "Do you support HIPAA / PCI-DSS / ISO 42001?" | Additional framework demand |
| "Can you integrate with Vanta/Drata?" | GRC tool integration requests |
| Enterprise inbound | Companies asking about pricing |

---

## 15. Launch Plan

### Show HN Draft

> **Show HN: AgentAudit — Turn your AI agent traces into EU AI Act compliance reports**
>
> EU AI Act enforcement hits August 2, 2026. Article 12 requires automatic audit logging for high-risk AI systems. Most teams already have observability (Langfuse, Laminar, Opik) but nobody bridges the gap between "we trace our agents" and "here's our compliance evidence for the regulator."
>
> AgentAudit is an open-source CLI that imports your existing agent traces and maps them against EU AI Act Article 12 and SOC 2 Trust Service Criteria. It tells you exactly what's compliant, what's missing, and how to fix the gaps. Generates auditor-ready PDF reports.
>
> Works with Langfuse, OTel exports, or any JSONL traces. No new SDK to install — uses the observability data you already have.
>
> `pip install agentaudit && agentaudit init`

### Distribution Channels

1. Show HN (target: Tuesday or Wednesday morning US time)
2. LangChain Discord — compliance-adjacent discussions
3. LinkedIn — AI governance groups, compliance professionals
4. r/EuropeanLaw, r/GDPR — regulatory audience
5. EU AI Act community forums
6. Compliance tool comparison blogs (pitch for inclusion)

---

## Appendix A: EU AI Act Article 12 — Full Requirements Map

| ID | Article | Requirement | What Must Exist in Traces |
|----|---------|-------------|--------------------------|
| A12-1 | 12(1) | Automatic recording of events | System-generated trace events without manual intervention |
| A12-2a | 12(2)(a) | Risk identification logging | Error events, anomaly markers, risk flags |
| A12-2b | 12(2)(b) | Post-market monitoring support | Sufficient detail for ongoing surveillance (Art. 72) |
| A12-2c | 12(2)(c) | Operational monitoring | Deployer can monitor via logs (Art. 26(5)) |
| A12-3a | 12(3)(a) | Session timestamps | Start/end datetime on every trace (biometric: mandatory; others: best practice) |
| A12-3b | 12(3)(b) | Reference database recording | Data sources used by the system |
| A12-3c | 12(3)(c) | Match input recording | Inputs that triggered matches/decisions |
| A12-3d | 12(3)(d) | Human verifier identification | Identity of humans verifying results (Art. 14(5)) |
| A14 | 14 | Human oversight | Human intervention points logged |
| A13 | 13 | Transparency | Users informed about logging practices |
| A11 | 11 | Technical documentation | Logging strategy documented |
| A26-log | 26 | Log retention | Minimum 6 months, available to authorities |
| A26-fin | 26 | Financial services | Logs maintained per financial services law |
| A72 | 72 | Post-market surveillance | Logs support ongoing monitoring |
| A79 | 79 | Risk reporting | Logs enable 72-hour incident reporting |
| EN-err | EN 18229-1 | Error capture | Error codes, severity, impact, context |
| EN-comp | EN 18229-1 | Component identification | Every event linked to system component |
| EN-ts | EN 18229-1 | Timestamp completeness | Every event timestamped |
| EN-flow | ISO 24970 | Data flow traceability | Inputs traceable through to outputs |

## Appendix B: SOC 2 CC Criteria Relevant to AI Agents

| ID | Criteria | Requirement | What Must Exist in Traces |
|----|----------|-------------|--------------------------|
| CC7.1 | System Operations | Detect/monitor for anomalies | Error events, anomaly detection evidence |
| CC7.2 | System Operations | Monitor for failures/errors | System failure and error logging |
| CC7.3 | System Operations | Evaluate detected events | Severity classification, triage evidence |
| CC7.4 | System Operations | Incident response | Sufficient context for incident investigation |
| CC7.5 | System Operations | Root cause analysis | Detailed traces enabling RCA |
| CC6.1 | Access Controls | Logical access security | Agent authentication/authorization logs |
| CC6.6 | Access Controls | System component access | API key usage, service account activity |
| CC8.1 | Change Management | Controlled changes | Agent/model version recorded in traces |
| CC5.1 | Control Activities | Risk mitigation controls | Security controls evidenced in traces |
| CC5.3 | Control Activities | Policies deployed | Human oversight policies executed and logged |
| CC3.2 | Risk Assessment | Risk identification | Traces support risk assessment activities |
| CC2.3 | Communication | Third-party communication | External API calls and responses logged |
| PI1.2 | Processing Integrity | Processing meets specs | Agent outputs match expected specifications |
| PI1.3 | Processing Integrity | Input completeness | All inputs recorded |
| PI1.4 | Processing Integrity | Output completeness | All outputs recorded |
| C1.1 | Confidentiality | Information identification | PII/sensitive data flagged and handled |

## Appendix C: Competitive Positioning (Updated March 31, 2026)

| Tool | What They Do | Relationship to AgentAudit |
|------|-------------|---------------------------|
| Langfuse | OSS LLM tracing (20K stars) | **Data source** — we import their traces |
| Laminar | OSS agent observability (2.7K stars) | **Data source** — we import their traces |
| Opik/Comet | OSS LLM eval + observability (18.5K stars) | **Data source** — we import their traces |
| Helicone | OSS LLM gateway (4.4K stars) | **Data source** — we import their data |
| AgentOps | OSS agent monitoring (MIT) | **Data source** — potential future adapter |
| Braintrust | Closed-source evaluation platform ($800M) | Not a data source (closed API) |
| Raindrop | Closed-source silent failure detection | Complementary — different problem |
| EuConform | EU AI Act risk classification (OSS) | Complementary — they do pre-deployment risk classification, we do runtime compliance |
| Vanta/Drata/Secureframe | GRC platforms | **Export targets** — our JSON reports feed into their platforms |
| AgentBouncr | Runtime governance layer | Complementary — they enforce, we audit |

**Our unique position:** We don't compete with any of the above. We sit between the observability tools (data sources) and the GRC platforms (report consumers), providing the compliance interpretation layer that neither side builds.

---

*End of specification.*

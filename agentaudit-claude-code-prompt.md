# AgentAudit — Claude Code Agent Teams Build Prompt (v5)

## What Changed from v4

v5 adds **harness-aware compliance assessment** — the ability to detect and evaluate multi-agent architectures (planner/generator/evaluator patterns, sprint contracts, context resets, inter-agent artifact handoffs, evaluator calibration). This is based on [Anthropic's harness design research](https://www.anthropic.com/engineering/harness-design-long-running-apps) showing that production AI systems use orchestration harnesses, not single agents. No competitor assesses compliance at the harness level.

AgentAudit now covers **6 compliance frameworks** (EU AI Act Art. 12, SOC 2 TSC, NIST AI RMF, ISO/IEC 42001, Colorado AI Act, OMB M-26-04) plus **harness architecture assessment**, training data governance, AI system inventory, bias audit tracking, and regulatory deadline awareness. The build uses **Claude Code Agent Teams** for parallel execution — 5 teammates working simultaneously instead of 4 sequential agents.

## How To Use This Document

### Prerequisites

1. Claude Code v2.1.32+ installed (`claude --version`)
2. Enable agent teams:
   ```json
   // ~/.claude/settings.json
   {
     "env": {
       "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
     }
   }
   ```
3. Python 3.11+ with `uv` or `pip` available
4. An empty git repo initialized: `mkdir agentaudit && cd agentaudit && git init`

### How to run

1. Copy **Step 1** (the agent definitions) into `.claude/agents/` as individual files
2. Copy **Step 2** (the team lead prompt) into a new Claude Code session
3. The lead spawns 5 teammates in parallel, coordinates work, and synthesizes results
4. After the team finishes, run **Step 3** (the verification prompt) in a new session

**Estimated build time:** 3-5 hours (parallel), down from 8-12 hours (sequential).

---

## Step 1: Agent Definitions

Create these 5 files in `.claude/agents/` before starting the team.

### `.claude/agents/scaffolder.md`

```markdown
---
name: scaffolder
description: Sets up the project structure, dependencies, data models, and import adapters for agentaudit. Use this agent for initial project scaffolding.
model: sonnet
tools: Read, Write, Edit, Bash, Glob, Grep
color: blue
---

You are building the foundation for "agentaudit" — an open-source Python CLI that imports AI agent traces from observability tools and generates multi-framework compliance reports.

## Your deliverables

### 1. Project scaffolding

Create this exact structure:

```
agentaudit/
├── pyproject.toml
├── README.md (placeholder — another teammate handles this)
├── src/
│   └── agentaudit/
│       ├── __init__.py          # version = "0.2.0"
│       ├── cli.py               # Typer CLI — placeholder, another teammate builds this
│       ├── models.py            # All Pydantic data models
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── base.py          # Abstract base adapter
│       │   ├── langfuse.py      # Langfuse REST API adapter
│       │   ├── otel.py          # OpenTelemetry JSONL adapter
│       │   └── jsonl.py         # Raw JSONL adapter
│       ├── engine/
│       │   ├── __init__.py      # placeholder
│       │   ├── article12.py     # placeholder
│       │   ├── soc2.py          # placeholder
│       │   ├── nist_rmf.py      # placeholder
│       │   ├── iso42001.py      # placeholder
│       │   ├── colorado.py      # placeholder
│       │   ├── omb_m2604.py     # placeholder
│       │   ├── harness.py       # placeholder — multi-agent harness assessment
│       │   ├── inventory.py     # placeholder
│       │   ├── training_data.py # placeholder
│       │   └── gap_analyzer.py  # placeholder
│       ├── reports/
│       │   ├── __init__.py      # placeholder
│       │   ├── pdf_report.py    # placeholder
│       │   └── html_report.py   # placeholder
│       └── rules/               # YAML compliance rule files
│           └── (placeholder)
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_adapters.py
│   └── fixtures/
│       ├── sample_langfuse.json
│       ├── sample_otel.jsonl
│       └── sample_raw.jsonl
└── examples/
    └── sample_traces.jsonl
```

### 2. pyproject.toml

```toml
[project]
name = "agentaudit"
version = "0.2.0"
description = "Multi-framework AI agent compliance assessment. Import traces, generate audit-ready reports."
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0",
    "typer[all]>=0.9",
    "httpx>=0.25",
    "pyyaml>=6.0",
    "fpdf2>=2.7",
    "jinja2>=3.1",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-asyncio", "ruff"]

[project.scripts]
agentaudit = "agentaudit.cli:app"
```

### 3. models.py — Complete data models

Define these Pydantic models:

```python
# EventType enum: node_execution, llm_call, tool_call, conditional_branch,
#   human_oversight, state_mutation, error, subgraph_entry, subgraph_exit,
#   data_provenance, bias_check, consumer_notification, model_card_ref,
#   # --- Harness-level events (multi-agent architecture) ---
#   agent_spawn,           # A harness spawning a sub-agent (planner, generator, evaluator)
#   agent_handoff,         # Artifact passed between agents (sprint contract, QA report, context reset doc)
#   context_reset,         # Full context window cleared with structured handoff
#   sprint_contract,       # Pre-implementation agreement between generator and evaluator
#   evaluation_pass,       # QA/evaluator agent assessment result (pass/fail per criterion)
#   evaluator_calibration  # Human tuning of evaluator prompt (judgment divergence correction)

# TraceEvent: event_id, trace_id, timestamp, event_type, node_name,
#   parent_event_id, input_data, output_data, duration_ms, metadata,
#   hash_prev, hash_self,
#   source_agent_id (optional — which agent in the harness produced this event),
#   target_agent_id (optional — for handoffs, which agent receives)

# Trace: trace_id, agent_name, agent_version, model_id, timestamp_start,
#   timestamp_end, status, risk_classification, events[]
#   Computed properties: total_llm_calls, total_tool_calls, total_tokens,
#   estimated_cost, has_human_oversight, has_errors, has_hash_chain,
#   has_data_provenance, has_bias_check, has_consumer_notification,
#   # --- Harness-aware computed properties ---
#   harness_topology (single_agent | generator_evaluator | planner_generator_evaluator | unknown),
#   has_sprint_contracts, has_evaluation_passes, has_context_resets,
#   has_evaluator_calibration, unique_agent_ids (set of source_agent_ids in events),
#   inter_agent_handoff_count

# ComplianceStatus: status (met|partial|not_met|not_applicable),
#   confidence, evidence_count, evidence_sample[], gap_description, remediation

# Gap: framework, requirement_id, requirement_name, article_or_code,
#   severity (critical|warning|info), current_state, required_state,
#   remediation_steps[], affected_traces, total_traces, enforcement_deadline

# AISystemInventoryEntry: system_id, system_name, description, risk_level,
#   deployment_date, owner, model_ids[], data_sources[], has_model_card,
#   has_risk_assessment, has_bias_audit

# HarnessTopology: topology_type (single_agent | generator_evaluator |
#   planner_generator_evaluator | custom), agent_roles[] (list of
#   {agent_id, role: planner|generator|evaluator|unknown}),
#   has_sprint_contracts, has_context_resets, has_evaluator_calibration,
#   handoff_artifact_count, evaluation_pass_count, context_reset_count

# ComplianceReport: generated_at, assessment_period_start, assessment_period_end,
#   data_source, traces_analyzed, events_analyzed, frameworks{},
#   harness_assessment (HarnessTopology + compliance status),
#   inventory, training_data_assessment, gaps[], overall_readiness_score
```

### 4. Import adapters

**base.py**: Abstract class with `async def import_traces(self, **kwargs) -> list[Trace]`

**langfuse.py**: Uses httpx to call Langfuse REST API:
- `GET /api/public/traces` with pagination
- `GET /api/public/observations?traceId=X` for each trace
- Maps Langfuse observations to TraceEvent models
- Auth via LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY env vars
- Handle pagination (limit/offset), date range filtering

**otel.py**: Reads OpenTelemetry JSONL export files:
- Parse each line as JSON, extract spans from resourceSpans
- Map gen_ai.* semantic conventions to TraceEvent
- Group spans by traceId into Trace objects
- Handle both gen_ai.content.prompt and gen_ai.content.completion attributes

**jsonl.py**: Reads raw JSONL where each line is a JSON object:
- Flexible mapping: detect schema automatically
- Support both flat events and nested trace objects
- Validate with Pydantic

### 5. Test fixtures

Create realistic test fixture files:
- `sample_langfuse.json`: Mock Langfuse API response with 3 traces, each having 4-6 observations
- `sample_otel.jsonl`: 3 OTel trace exports with gen_ai.* attributes
- `sample_raw.jsonl`: 3 raw trace events

### 6. Tests

Write tests for:
- All Pydantic model validation (valid + invalid data)
- Each adapter's parsing logic using the fixtures
- Trace computed properties

Run `pytest tests/` and ensure all tests pass before marking your tasks complete.

## Critical rules
- Use Pydantic v2 model_validator where needed
- All timestamps must be timezone-aware (UTC)
- Every adapter must handle empty/malformed input gracefully
- Do NOT write code for the engine/, reports/, or cli.py beyond placeholder __init__.py files — other teammates own those
```

### `.claude/agents/compliance-engine.md`

```markdown
---
name: compliance-engine
description: Builds the compliance assessment engine for agentaudit — all 6 framework assessors, AI inventory checker, training data governance, and gap analyzer. Use this agent for compliance logic.
model: sonnet
tools: Read, Write, Edit, Bash, Glob, Grep
color: green
---

You are building the compliance assessment engine for "agentaudit". This is the core intelligence — it takes imported traces and evaluates them against 6 regulatory frameworks, multi-agent harness architecture patterns, training data governance, and AI system inventory checks.

## Key Concept: Harness-Aware Compliance

Production AI systems increasingly use multi-agent harness architectures (planner → generator → evaluator) rather than single agents. Based on Anthropic's harness design research (https://www.anthropic.com/engineering/harness-design-long-running-apps):

- **Generator-Evaluator pattern**: Separate agents for creation and assessment, inspired by GANs. Reduces self-evaluation bias. The evaluator doesn't judge its own work.
- **Sprint contracts**: Pre-implementation agreements between generator and evaluator with specific success criteria (e.g., 27+ criteria per sprint). Machine-readable test plans.
- **Context resets**: Full context window cleared with structured handoff artifacts. Breaks trace continuity — needs meta-trace linking.
- **Evaluator calibration**: Human reads evaluator logs, identifies judgment divergences, updates QA prompt. This IS the human oversight Article 14 requires.
- **Inter-agent artifact handoffs**: Agents exchange work via files/messages, not shared context. Each handoff is a compliance-relevant event.

AgentAudit is the ONLY tool that assesses compliance at the harness orchestration level, not just individual agent traces. This is the key differentiator.

IMPORTANT: Wait for the scaffolder teammate to finish models.py before writing assessment code. You can start writing YAML rule files and planning immediately. Read src/agentaudit/models.py to understand the data models before coding.

## Your deliverables

### 1. YAML compliance rule files

Create these in `src/agentaudit/rules/`:

**article12.yaml** — 12 requirements:
```yaml
framework: "EU AI Act"
framework_id: "eu_ai_act_art12"
enforcement_date: "2026-08-02"
penalty: "EUR 35 million or 7% of global annual turnover"
requirements:
  - id: art12_automatic_logging
    name: "Automatic Recording of Events"
    article: "Art. 12(1)"
    description: "High-risk AI systems shall technically allow for the automatic recording of events (logs) over the lifetime of the system."
    severity_if_missing: critical
    check_type: trace_coverage
    threshold: 0.95
  # ... (define all 12)
```

Map these requirements (use the same IDs as the demo HTML report):
1. art12_automatic_logging — Art. 12(1)
2. art12_risk_identification — Art. 12(2)(a)
3. art12_post_market_monitoring — Art. 12(2)(b)
4. art12_operational_monitoring — Art. 12(2)(c)
5. art12_session_timestamps — Art. 12(3)(a)
6. art12_input_recording — Art. 12(3)(c)
7. art14_human_oversight — Art. 14
8. art26_log_retention — Art. 26
9. art72_incident_support — Art. 72/79
10. en_component_identification — EN 18229-1
11. en_timestamp_completeness — EN 18229-1
12. tamper_evidence — EN 18229-1 implied

**soc2.yaml** — 9 criteria (CC7.1, CC7.2, CC7.3, CC7.5, CC5.3, CC8.1, CC2.3, PI1.3, PI1.4)

**nist_rmf.yaml** — 8 requirements across GOVERN, MAP, MEASURE, MANAGE:
1. govern_risk_policies — AI risk policies documented
2. govern_roles — Roles and responsibilities defined
3. map_context — AI system context documented
4. map_stakeholder_impact — Stakeholder impact assessed
5. measure_performance — Performance metrics tracked
6. measure_bias — Bias and fairness evaluation
7. manage_incident — Incident response procedures
8. manage_monitoring — Continuous monitoring active

**iso42001.yaml** — 6 clauses (5.1, 6.1, 7.2, 8.1, 9.1, 10.1)

**colorado.yaml** — 6 requirements:
1. algorithmic_impact_assessment
2. consumer_notification
3. decision_explanation
4. training_data_disclosure
5. opt_out_mechanism
6. adverse_decision_audit_trail
- enforcement_date: "2026-07-01"

**omb_m2604.yaml** — 5 requirements:
1. model_card
2. system_card
3. evaluation_artifacts
4. human_review_points
5. acceptable_use_policy

**harness.yaml** — 8 requirements for multi-agent architecture assessment:
```yaml
framework: "Harness Architecture"
framework_id: "harness_architecture"
description: "Assesses multi-agent orchestration patterns for compliance readiness. Based on Anthropic's harness design principles."
requirements:
  - id: harness_topology_detected
    name: "Harness Topology Identification"
    description: "System can identify whether traces represent a single agent, generator-evaluator pair, or planner-generator-evaluator harness"
    severity_if_missing: warning
    check_type: topology_detection
  - id: inter_agent_handoffs_logged
    name: "Inter-Agent Artifact Handoffs Logged"
    description: "Handoff artifacts between agents (sprint contracts, QA reports, context docs) are captured as structured events, not freeform text"
    severity_if_missing: critical
    article: "Art. 12(1) + CC2.3"
  - id: context_reset_continuity
    name: "Context Reset Trace Continuity"
    description: "When context windows are reset, a meta-trace links the handoff artifact from session N to session N+1, preserving audit trail continuity"
    severity_if_missing: critical
    article: "Art. 12(1)"
  - id: sprint_contract_documented
    name: "Sprint Contracts Documented"
    description: "Pre-implementation agreements between generator and evaluator with specific success criteria are logged as structured artifacts"
    severity_if_missing: warning
    article: "CC8.1 + Art. 12(2)(c)"
  - id: evaluation_pass_recorded
    name: "Evaluation Results Recorded"
    description: "QA/evaluator agent pass/fail results per criterion are logged with specific code locations and evidence"
    severity_if_missing: warning
    article: "CC7.3 + Art. 12(2)(a)"
  - id: evaluator_calibration_evidence
    name: "Evaluator Calibration Evidence"
    description: "Human tuning of evaluator prompts — judgment divergence logs, prompt version history, calibration examples — constitutes Article 14 human oversight evidence"
    severity_if_missing: critical
    article: "Art. 14"
  - id: agent_role_separation
    name: "Agent Role Separation Verified"
    description: "Generator and evaluator are separate agents (not self-evaluating). Reduces self-evaluation bias per Anthropic research."
    severity_if_missing: warning
  - id: harness_cost_tracking
    name: "Per-Agent Cost and Duration Tracking"
    description: "Token usage, cost, and duration tracked per agent role (planner, generator, evaluator) for operational monitoring"
    severity_if_missing: warning
    article: "Art. 12(2)(c) + ISO 42001 9.1"
```

### 2. Assessment engine modules

Each file in `src/agentaudit/engine/` follows this pattern:

```python
# Load the YAML rules at module level
# Define assess_<framework>(traces: list[Trace], rules: dict) -> dict[str, ComplianceStatus]
# Each check function inspects traces and returns ComplianceStatus with evidence
```

**article12.py**: `assess_article12(traces) -> dict[str, ComplianceStatus]`
- Implement all 12 checks from the demo (automatic logging, risk ID, post-market monitoring, operational monitoring, session timestamps, input recording, human oversight, log retention, incident support, component ID, timestamp completeness, tamper evidence)
- Log retention check: compute trace span in days, compare to 180-day threshold
- Tamper evidence: count traces with hash_prev set on events

**soc2.py**: `assess_soc2(traces) -> dict[str, ComplianceStatus]`
- 9 checks from the demo

**nist_rmf.py**: `assess_nist_rmf(traces) -> dict[str, ComplianceStatus]`
- GOVERN: check for policy_ref in metadata, reviewer roles
- MAP: check for agent context, risk_classification field
- MEASURE: check for performance metrics (tokens, cost, latency, confidence)
- MANAGE: check for error events with severity, continuous monitoring span

**iso42001.py**: `assess_iso42001(traces) -> dict[str, ComplianceStatus]`
- 5.1: leadership/governance policy references
- 6.1: risk assessment artifacts (risk_classification field)
- 7.2: training/competency records
- 8.1: operational planning (structured workflows with defined nodes)
- 9.1: performance monitoring
- 10.1: continual improvement artifacts

**colorado.py**: `assess_colorado(traces) -> dict[str, ComplianceStatus]`
- Check for consumer_notification events, opt-out events, impact assessments
- Check for training data disclosure metadata
- Check for decision explanation capability (conditional branches with reasoning)

**omb_m2604.py**: `assess_omb_m2604(traces) -> dict[str, ComplianceStatus]`
- Check for model_card_ref events, system card metadata
- Check for evaluation artifacts
- Check for human review points, acceptable use policy references

**harness.py**: `assess_harness(traces) -> dict[str, ComplianceStatus]`

This is the most novel and differentiating module. It assesses multi-agent harness architecture patterns:

```python
def detect_topology(traces: list[Trace]) -> HarnessTopology:
    """Detect the harness architecture from trace patterns."""
    # 1. Count unique agent IDs across all events (source_agent_id field)
    # 2. Look for agent_spawn events to identify roles (planner, generator, evaluator)
    # 3. Classify:
    #    - 1 agent ID or no agent IDs → single_agent
    #    - 2 agent IDs + evaluation_pass events → generator_evaluator
    #    - 3+ agent IDs + sprint_contract events → planner_generator_evaluator
    #    - Multiple agents but no clear pattern → custom
    # 4. Return HarnessTopology with agent roles, counts, and flags

def assess_harness(traces: list[Trace]) -> dict[str, ComplianceStatus]:
    """Assess multi-agent harness compliance."""
    topology = detect_topology(traces)
    results = {}
    
    # harness_topology_detected: Can we identify the architecture?
    # If single_agent: status=met (simple case, fully traceable)
    # If generator_evaluator or planner_generator_evaluator: status=met
    # If custom with no agent_spawn events: status=partial (architecture unclear)
    
    # inter_agent_handoffs_logged: Are agent_handoff events present?
    # For multi-agent topologies: check handoff count > 0
    # For single_agent: status=not_applicable
    
    # context_reset_continuity: For each context_reset event, does the
    # next event in the trace reference the reset's handoff artifact?
    # Check: context_reset events have output_data with handoff_doc_id,
    # and the next event's input_data references that same handoff_doc_id
    
    # sprint_contract_documented: Are sprint_contract events present?
    # Check: events have input_data with criteria list and agreed=True
    
    # evaluation_pass_recorded: Are evaluation_pass events present?
    # Check: events have output_data with per-criterion pass/fail results
    # Bonus: check that evaluator agent_id != generator agent_id (separation)
    
    # evaluator_calibration_evidence: Are evaluator_calibration events present?
    # This is the strongest Article 14 evidence — human tuning evaluator judgment
    # Check: events have metadata with prompt_version, divergence_description,
    # calibration_examples
    
    # agent_role_separation: Verify generator != evaluator
    # Check: evaluation_pass events have source_agent_id different from
    # the agent_id that produced the content being evaluated
    
    # harness_cost_tracking: Is cost/duration tracked per agent role?
    # Check: events have metadata with cost_usd and duration_ms broken
    # down by agent role, not just aggregated
    
    return results
```

Key compliance mappings for harness architecture:
- **Evaluator calibration → Article 14 human oversight**: The human tuning loop (read evaluator logs → identify divergences → update prompt) IS human oversight. This is stronger evidence than rubber-stamp approvals.
- **Sprint contracts → SOC 2 CC8.1 change management**: Pre-agreed success criteria with documented pass/fail results.
- **Context resets → Article 12(1) continuity**: If context windows are cleared without linking, the audit trail has gaps.
- **Agent role separation → Reducing self-evaluation bias**: Separate evaluator provides independent quality assurance, not self-grading.
- **Per-agent cost tracking → ISO 42001 9.1 performance monitoring**: Operational costs per phase enable efficiency governance.

**inventory.py**: `assess_inventory(traces) -> AISystemInventoryEntry`
- Auto-generate inventory entry from traces (agent_name, model_ids, tool usage)
- Flag missing fields (risk_classification, model_card, bias_audit)

**training_data.py**: `assess_training_data(traces) -> dict[str, ComplianceStatus]`
- 5 checks: provenance tracking, pre-pipeline validation, data removal capability, audit log completeness, bias testing documentation
- Include industry benchmark comparisons (78% can't validate, etc.)

**gap_analyzer.py**: `analyze_gaps(all_results, total_traces) -> list[Gap]`
- Merge gaps from all 6 frameworks + harness assessment + inventory + training data
- Sort by: enforcement_deadline (soonest first), then severity (critical > warning > info)
- Attach remediation steps from YAML rules
- Compute overall_readiness_score: weighted average across frameworks

### 3. Score calculator

Add to `__init__.py` or a shared utils:
```python
def calc_score(results: dict[str, ComplianceStatus]) -> float:
    """met=1.0, partial=0.5, not_met=0.0, not_applicable=excluded"""
```

### 4. Tests

Write `tests/test_engine.py`:
- Test each assessor with known-good and known-bad trace sets
- Test gap analyzer sorting and severity classification
- Test score calculator edge cases
- Use the sample trace generator (ask the demo-builder teammate for it or write your own)

Run `pytest tests/test_engine.py` — all must pass.

## Critical rules
- Load YAML rules at import time, not per-call
- Every check must return ComplianceStatus with meaningful evidence_sample
- Never hardcode thresholds — read from YAML rules
- Gap severity must respect enforcement deadlines (Colorado July 1 > EU Aug 2 > others)
- Do NOT touch adapters/, reports/, or cli.py
```

### `.claude/agents/report-builder.md`

```markdown
---
name: report-builder
description: Builds the PDF and HTML report generators for agentaudit compliance reports. Use this agent for report generation code.
model: sonnet
tools: Read, Write, Edit, Bash, Glob, Grep
color: purple
---

You are building the report generators for "agentaudit". Your job is to produce professional, audit-ready compliance reports in both PDF and HTML formats.

IMPORTANT: Wait for the compliance-engine teammate to finish the engine modules. You need to import ComplianceStatus, Gap, and the score calculator. Read src/agentaudit/models.py and src/agentaudit/engine/ to understand the data structures.

## Reference

Use this HTML report as your design reference — it represents the exact output quality and content structure we need:

Read the file at: the existing HTML report in the outputs directory if available, otherwise follow the spec below.

## Your deliverables

### 1. html_report.py

Generate a single-file HTML compliance report using Jinja2 templates. The report MUST include ALL of these sections:

1. **Header**: Title, frameworks listed, assessment period, generation date
2. **Urgency banner**: Red gradient banner showing days until next enforcement deadline (calculate from today). Show EU AI Act Aug 2 2026 and Colorado July 1 2026 deadlines.
3. **Framework score boxes**: 7 color-coded boxes (green ≥80%, yellow ≥50%, red <50%) for each framework INCLUDING Harness Architecture
4. **Key stats**: Traces analyzed, total events, critical gaps count, requirements met / total
5. **Market context box**: Blue info box with key market statistics:
   - "$2.55B AI governance market in 2026, growing 45.3% CAGR"
   - "73% of enterprises deploy AI but only 7% govern in real time"
   - "83% lack formal AI system inventories"
   - "78% cannot validate training data origins"
   - "Production AI systems increasingly use multi-agent harness architectures — planner/generator/evaluator patterns — that existing observability tools cannot trace"
6. **Regulatory deadlines timeline**: Cards for Colorado (July 1), EU AI Act (Aug 2), OMB (effective now), GPAI (Aug 2027), Canada AIDA (TBD)
7. **Harness Architecture Assessment** (NEW — place prominently after deadlines):
   - Detected topology visualization: show whether system is single-agent, generator-evaluator, or planner-generator-evaluator
   - Visual diagram or description of agent roles and handoff flow
   - 8-row assessment table from harness.yaml
   - Highlight: evaluator calibration as Article 14 human oversight evidence
   - Highlight: sprint contracts as CC8.1 change management evidence
   - Highlight: context reset continuity for audit trail completeness
   - Call-out box: "Why harness assessment matters: Self-evaluating agents exhibit evaluation bias — they confidently praise mediocre work. Separate evaluator agents with human-calibrated judgment provide genuine quality assurance."
8. **AI System Inventory assessment**: 3 metric cards (systems registered, risk classifications, model cards) with progress bars
9. **Training Data Governance table**: 5 controls with status, your state, and industry benchmark column
10. **EU AI Act Article 12 table**: 12 rows with requirement, article, status badge (MET/PARTIAL/GAP), evidence
11. **SOC 2 TSC table**: 9 rows
12. **NIST AI RMF table**: 8 rows across GOVERN/MAP/MEASURE/MANAGE
13. **ISO/IEC 42001 table**: 6 rows
14. **Colorado AI Act table**: 6 rows — note July 1 deadline prominently
15. **OMB M-26-04 table**: 5 rows
16. **Gap analysis cards**: Sorted by deadline then severity, each with expandable remediation steps
17. **Competitive landscape**: Two-column grid — observability tools vs governance platforms with positioning note: "AgentAudit is the only tool that assesses compliance at the harness orchestration level, not just individual agent traces"
18. **Methodology footer**: Data source, traces, events, period, all 7 frameworks (including Harness Architecture) with requirement counts, confidence level, disclaimer

Style requirements:
- Light mode only (white background, no dark mode media queries)
- Clean, professional aesthetic using system fonts
- Color-coded status badges: green (#16a34a) for MET, yellow (#ca8a04) for PARTIAL, red (#dc2626) for GAP
- Responsive grid layout (works on mobile)
- Print-friendly with @media print rules
- Single file — all CSS inline in <style>, no external dependencies
- Use Jinja2 template stored as a Python string constant

### 2. pdf_report.py

Generate a PDF compliance report using fpdf2 with these pages:

1. **Cover page**: Title, subtitle (all 7 frameworks including Harness Architecture), assessment period, report date, data source, traces/events count, agent name
2. **Executive summary**: Score boxes for all 7 frameworks, key stats, summary paragraph
3. **Regulatory deadlines**: Table of upcoming enforcement dates
4. **Harness Architecture assessment**: Detected topology, 8-row table, cross-references to Art. 14 and CC8.1
5. **AI System Inventory**: Registration status, risk classification gaps, model card status
6. **Training Data Governance**: 5-row assessment table with industry benchmarks
7. **EU AI Act Article 12 assessment**: Full 12-row table
8. **SOC 2 assessment**: 9-row table
9. **NIST AI RMF assessment**: 8-row table
10. **ISO/IEC 42001 assessment**: 6-row table
11. **Colorado AI Act assessment**: 6-row table
12. **OMB M-26-04 assessment**: 5-row table
13. **Gap analysis**: All gaps with severity badges, current state, remediation steps
14. **Methodology**: Full assessment methodology and disclaimers

PDF styling:
- Headers and footers on every page (except cover)
- Color-coded status cells (green/yellow/red fill)
- Page breaks between major sections
- Professional typography (Helvetica, proper spacing)
- "Generated by AgentAudit v0.2.0" in footer

### 3. Tests

Write `tests/test_reports.py`:
- Test HTML generation produces valid HTML (check for key section headings)
- Test PDF generation creates a valid file (non-zero size, starts with %PDF)
- Test with edge cases: zero gaps, all gaps, empty traces

Run `pytest tests/test_reports.py` — all must pass.

## Critical rules
- Reports must be audit-ready — something you'd hand to a Big 4 auditor
- Every data point must come from the ComplianceReport model — no hardcoded values
- The urgency banner days-until-deadline must be computed dynamically from datetime.now()
- Market context stats can be hardcoded (they're industry benchmarks, not trace-derived)
- Do NOT touch adapters/ or engine/
```

### `.claude/agents/cli-builder.md`

```markdown
---
name: cli-builder
description: Builds the Typer CLI interface and sample trace generator for agentaudit. Use this agent for the CLI and demo data generation.
model: sonnet
tools: Read, Write, Edit, Bash, Glob, Grep
color: orange
---

You are building the CLI interface and sample trace generator for "agentaudit".

IMPORTANT: Wait for scaffolder, compliance-engine, and report-builder to finish their core work. You integrate everything. Read the finished modules before writing CLI code.

## Your deliverables

### 1. cli.py — Full Typer CLI

```python
import typer
app = typer.Typer(name="agentaudit", help="Multi-framework AI agent compliance assessment")
```

Commands:

**`agentaudit assess`** — Main command
```
agentaudit assess \
  --source langfuse|otel|jsonl \
  --langfuse-host https://cloud.langfuse.com \
  --langfuse-public-key pk-... \
  --langfuse-secret-key sk-... \
  --otel-file traces.jsonl \
  --jsonl-file raw.jsonl \
  --output-dir ./reports \
  --format pdf,html,json,csv \
  --frameworks all|eu-ai-act,soc2,nist,iso42001,colorado,omb \
  --days 90
```

Flow:
1. Import traces using the selected adapter
2. Run all selected framework assessments
3. Run inventory + training data governance checks
4. Analyze gaps
5. Generate reports in all requested formats
6. Print summary to terminal with Rich tables

**`agentaudit demo`** — Generate sample data + reports
```
agentaudit demo --output-dir ./demo-reports --traces 50
```

Flow:
1. Generate sample traces using the built-in generator
2. Run full assessment pipeline
3. Output PDF + HTML to the specified directory
4. Print summary

**`agentaudit inventory`** — List discovered AI systems
```
agentaudit inventory --source langfuse --langfuse-host ... --langfuse-public-key ... --langfuse-secret-key ...
```

### 2. Sample trace generator — `src/agentaudit/demo.py`

Generate N realistic sample traces. This is the DEMO that compliance officers will see, so it must be convincing.

```python
def generate_sample_traces(n: int = 50) -> list[Trace]:
```

Generate traces that simulate BOTH single-agent AND multi-agent harness architectures:

**Mix of agent architectures** (this is what makes the demo unique):
- 60% of traces: **Single-agent** — standard LangGraph research agent (node_execution → llm_call → tool_call → synthesis)
- 25% of traces: **Generator-Evaluator pair** — generator produces output, evaluator assesses it. Include agent_spawn, agent_handoff, evaluation_pass events with separate source_agent_ids.
- 15% of traces: **Planner-Generator-Evaluator** — planner creates spec, generator implements in sprints, evaluator runs QA. Include sprint_contract events with criteria lists, evaluation_pass events with per-criterion pass/fail.

**Agent names**: Vary across ["research_writer_agent", "customer_support_agent", "document_classifier_agent", "claims_processor_agent", "risk_assessment_agent"]
**Model IDs**: Mix of claude-sonnet-4-6, gpt-4o, claude-haiku-4-5
**Event types**: Realistic mix including all new harness events

**Compliance characteristics that create REALISTIC gaps**:
  - 30% of traces have human_oversight events
  - 60% have hash-chain integrity
  - 10% have errors with severity classification
  - 5% have data_provenance events (to show the training data gap)
  - 0% have consumer_notification events (Colorado gap)
  - 0% have model_card_ref events (OMB gap)
  - 15% have bias_check events
  - 0% have risk_classification set (ISO 42001 gap)
  - Some traces include policy_ref in metadata (20%)
  - agent_version logged in 40% of events
  **Harness-specific characteristics**:
  - Of the multi-agent traces (40% of total):
    - 70% have agent_handoff events (but 30% are missing them — gap)
    - 50% have sprint_contract events
    - 40% have evaluation_pass events with per-criterion results
    - 10% have evaluator_calibration events (shows the human oversight gap)
    - 20% have context_reset events, but only half link to the next session (continuity gap)
    - Generator and evaluator have DIFFERENT source_agent_ids (role separation met)
    - Cost/duration tracked per-agent in only 30% of multi-agent traces

**Realistic metadata**: token counts, costs, confidence scores, tool names (web_search, database_query, document_retrieval, playwright_test), model versions
**Timestamps**: Spread over 90 days (creating the Art. 26 retention gap)
**Errors**: CONTEXT_OVERFLOW, RATE_LIMIT, TOOL_TIMEOUT with tracebacks

The scores should land approximately at:
- EU AI Act Art. 12: ~83%
- SOC 2: ~83%
- NIST AI RMF: ~62%
- ISO/IEC 42001: ~50%
- Colorado AI Act: ~33%
- OMB M-26-04: ~40%
- **Harness Architecture: ~44%** (topology detected, role separation OK, but missing handoff logging, context reset continuity, evaluator calibration, and per-agent cost tracking)

These scores make the demo compelling — the org is decent on basic logging (what they already have) but terrible on governance, inventory, harness-level observability, and newer regulations (what they need AgentAudit to tell them). The harness score is particularly powerful: it shows compliance officers that even organizations using sophisticated multi-agent architectures have massive gaps in how they trace and govern the orchestration layer.

### 3. Rich terminal output

When `agentaudit assess` or `agentaudit demo` runs, print to terminal:
- Progress bars during trace import and assessment
- Framework scores as a Rich table with color-coded cells
- Critical gaps highlighted in red
- "Run `agentaudit assess --help` for options" at the end

### 4. Integration tests

Write `tests/test_cli.py`:
- Test `agentaudit demo` end-to-end (generates files)
- Test `agentaudit assess --source jsonl --jsonl-file fixtures/sample_raw.jsonl`
- Test CLI help output

### 5. JSON + CSV export

Add to reports or as part of CLI:
- `--format json`: Dump the full ComplianceReport as JSON
- `--format csv`: Gap list as CSV (for import into GRC tools like ServiceNow, Archer)

Run all tests: `pytest tests/` — everything must pass.

## Critical rules
- The demo command must work with ZERO configuration — no API keys, no files
- Sample traces must produce realistic, varied compliance scores across all 6 frameworks
- Terminal output must look professional — use Rich tables, progress bars, and color
- Do NOT modify engine/ or reports/ logic — only import and call them
```

### `.claude/agents/docs-launcher.md`

```markdown
---
name: docs-launcher
description: Writes README, examples, and launch preparation for agentaudit. Use this agent for documentation and final polish.
model: sonnet
tools: Read, Write, Edit, Bash, Glob, Grep
color: cyan
---

You are writing the documentation, examples, and launch materials for "agentaudit". This is what potential users and compliance officers see first.

IMPORTANT: Wait for ALL other teammates to finish. Read the complete codebase before writing docs. Run `agentaudit demo` yourself to verify it works and see the actual output.

## Your deliverables

### 1. README.md

Write a compelling, professional README with:

**Above the fold** (what you see without scrolling):
```
# AgentAudit

The only compliance tool that understands multi-agent architectures. Import traces, assess 7 frameworks, get audit-ready reports in 30 seconds.

> EU AI Act Article 12 enforcement begins August 2, 2026. 78% of enterprises are unprepared.
> Production AI now runs on multi-agent harnesses — planner/generator/evaluator patterns —
> that existing observability tools can't trace. AgentAudit can.

## Quick Start
pip install agentaudit
agentaudit demo --output-dir ./my-reports
# Open my-reports/agentaudit-compliance-report.html
```

**Sections**:
1. What is AgentAudit? (3 sentences max — emphasize harness-aware as unique)
2. Quick Start (pip install + demo command)
3. Why Harness-Aware? (brief explanation: single-agent tracing misses the orchestration layer where compliance failures actually happen — inter-agent handoffs, sprint contracts, evaluator calibration, context resets)
4. Frameworks Covered (table: 7 frameworks including Harness Architecture, with enforcement dates)
5. How It Works (3-step: Import → Assess → Report, with diagram)
6. Usage Examples:
   - From Langfuse
   - From OpenTelemetry
   - From raw JSONL
   - Custom frameworks (YAML)
7. Report Formats (PDF, HTML, JSON, CSV — with screenshot descriptions)
8. Architecture (brief: adapters → engine (including harness detector) → reports)
9. Compliance Rules (how to read/edit YAML rules, including harness.yaml)
10. Roadmap (Phase 2: Dashboard, real-time harness monitoring, GRC integrations, live Playwright test observation)
10. Contributing
11. License (Apache 2.0)

### 2. Examples directory

**examples/langfuse_example.py**:
```python
"""Import traces from Langfuse and generate a compliance report."""
from agentaudit.adapters.langfuse import LangfuseAdapter
from agentaudit.engine import assess_all
from agentaudit.reports.html_report import generate_html_report
# ... full working example
```

**examples/otel_example.py**: Same pattern with OTel adapter
**examples/custom_rules.yaml**: Example of adding a custom compliance rule

### 3. COMPLIANCE_PRIMER.md

A 1-page plain-language summary for compliance officers (non-technical):
- What this tool does and doesn't do
- Which regulations it covers and their deadlines
- What a compliance officer needs to know about AI agent observability
- How to interpret the report scores
- Recommended next steps after reading a report
- Disclaimer: not legal advice

### 4. Final verification

Run these checks and fix any issues:
1. `agentaudit demo --output-dir /tmp/test-reports` works cleanly
2. `agentaudit demo --traces 100` works with more traces
3. PDF and HTML reports are generated and look professional
4. `pytest tests/` all pass
5. `ruff check src/` passes (or fix lint issues)
6. README code examples actually work
7. All imports resolve correctly

## Critical rules
- README must be concise and scannable — compliance officers won't read walls of text
- COMPLIANCE_PRIMER.md must avoid all jargon — write for a non-technical reader
- Do NOT modify any source code logic — only docs and examples
- If you find bugs during verification, message the responsible teammate to fix them
```

---

## Step 2: Team Lead Prompt

Copy this into a new Claude Code session to start the team:

```
Create an agent team to build "agentaudit" — a multi-framework AI agent compliance assessment CLI.

The project structure and agent roles are already defined in .claude/agents/. Spawn 5 teammates:

1. **scaffolder** — Project structure, data models, import adapters, and tests
2. **compliance-engine** — All 6 framework assessors, YAML rules, gap analyzer, inventory, and training data checks
3. **report-builder** — PDF and HTML report generators
4. **cli-builder** — Typer CLI, sample trace generator, Rich terminal output
5. **docs-launcher** — README, examples, compliance primer, final verification

## Execution order and dependencies

Phase 1 (immediate, parallel):
- scaffolder starts immediately
- compliance-engine starts writing YAML rule files immediately (no code dependency)

Phase 2 (after scaffolder finishes models.py):
- compliance-engine writes assessment code (needs models.py)
- report-builder starts (needs models.py)

Phase 3 (after compliance-engine and report-builder finish):
- cli-builder integrates everything

Phase 4 (after all others finish):
- docs-launcher writes docs and runs final verification

## Task breakdown

Create these tasks and assign them:

### scaffolder tasks:
1. Create project scaffolding and pyproject.toml
2. Write models.py with all Pydantic data models
3. Build Langfuse import adapter with tests
4. Build OTel JSONL import adapter with tests
5. Build raw JSONL import adapter with tests
6. Create test fixtures and run all adapter tests

### compliance-engine tasks:
7. Write all 7 YAML compliance rule files (including harness.yaml)
8. Build Article 12 assessor (article12.py)
9. Build SOC 2 assessor (soc2.py)
10. Build NIST AI RMF assessor (nist_rmf.py)
11. Build ISO 42001 + Colorado + OMB assessors
12. Build harness architecture assessor (harness.py) — topology detection + 8 checks
13. Build inventory checker, training data assessor, and gap analyzer
14. Write and run engine tests

### report-builder tasks:
15. Build HTML report generator with Jinja2 — including harness architecture section (depends on task 2)
16. Build PDF report generator with fpdf2 — including harness architecture section (depends on task 2)
17. Write and run report tests

### cli-builder tasks:
18. Build sample trace generator — demo.py with multi-agent harness traces (depends on task 2)
19. Build Typer CLI with assess + demo + inventory commands (depends on tasks 8-14, 15-16)
20. Add JSON and CSV export formats
21. Write and run CLI integration tests

### docs-launcher tasks:
22. Write README.md — emphasize harness-aware compliance as differentiator (depends on tasks 18-21)
23. Write examples and COMPLIANCE_PRIMER.md (depends on tasks 18-21)
24. Run final verification — all tests, lint, demo command (depends on all)

## Coordination rules

- scaffolder MUST finish models.py first (task 2) — broadcast when done
- compliance-engine and report-builder can start YAML/planning while waiting
- cli-builder should NOT start task 18 until engine and reports are done
- docs-launcher waits for everyone, then verifies the whole thing works
- If any teammate finds a bug in another's code, message them directly
- Require plan approval for the cli-builder before they start integration

## Quality gates

- Every teammate must run their own tests before marking tasks complete
- The docs-launcher runs the full test suite as the final gate
- The demo command (`agentaudit demo`) must produce professional reports with zero errors

Use Sonnet for all teammates. Start now.
```

---

## Step 3: Verification Prompt

After the team finishes, run this in a fresh Claude Code session:

```
You are verifying the "agentaudit" project built by an agent team. Run a thorough quality check:

1. Run the full test suite:
   pytest tests/ -v

2. Run the demo:
   cd agentaudit
   python -m agentaudit.cli demo --output-dir /tmp/agentaudit-verify

3. Check the generated reports:
   - Open the HTML file and verify all 6 framework sections are present
   - Verify the PDF was generated (non-zero size)
   - Check the JSON export if available

4. Run lint:
   ruff check src/

5. Verify these specific things:
   - Urgency banner shows correct days until Aug 2, 2026
   - Colorado deadline (July 1, 2026) appears before EU deadline
   - Training data governance section has industry benchmarks
   - AI system inventory section shows gaps
   - Harness architecture section shows detected topology (should detect mix of single-agent and multi-agent)
   - Harness assessment shows 8 requirements with realistic gaps (especially evaluator calibration and context reset continuity)
   - Multi-agent traces have different source_agent_ids for generator vs evaluator
   - Gap analysis is sorted by enforcement deadline
   - All 54 requirements are assessed (12 + 9 + 8 + 6 + 6 + 5 + 8)
   - Score calculator handles edge cases (zero traces, all met, all gap)
   - YAML rule files load correctly (including harness.yaml)

6. If any issues found, fix them and re-run tests.

7. Generate a final summary: what works, what needs attention, overall readiness for demo.
```

---

## Architecture Reference

```
agentaudit/
├── src/agentaudit/
│   ├── models.py           ← scaffolder
│   ├── cli.py              ← cli-builder
│   ├── demo.py             ← cli-builder
│   ├── adapters/           ← scaffolder
│   │   ├── langfuse.py
│   │   ├── otel.py
│   │   └── jsonl.py
│   ├── engine/             ← compliance-engine
│   │   ├── article12.py
│   │   ├── soc2.py
│   │   ├── nist_rmf.py
│   │   ├── iso42001.py
│   │   ├── colorado.py
│   │   ├── omb_m2604.py
│   │   ├── harness.py      ← KEY DIFFERENTIATOR: multi-agent architecture assessment
│   │   ├── inventory.py
│   │   ├── training_data.py
│   │   └── gap_analyzer.py
│   ├── reports/            ← report-builder
│   │   ├── html_report.py
│   │   └── pdf_report.py
│   └── rules/              ← compliance-engine
│       ├── article12.yaml
│       ├── soc2.yaml
│       ├── nist_rmf.yaml
│       ├── iso42001.yaml
│       ├── colorado.yaml
│       ├── omb_m2604.yaml
│       └── harness.yaml    ← multi-agent architecture rules
├── tests/                  ← each teammate writes their own
├── examples/               ← docs-launcher
├── README.md               ← docs-launcher
└── COMPLIANCE_PRIMER.md    ← docs-launcher
```

## Token Cost Estimate

5 teammates x ~35 min active each = ~175 minutes of Sonnet. Expect $18-35 in API costs depending on context sizes. This is significantly cheaper than building sequentially (which would run 10-14 hours of context across 4 sessions).

## Key Differentiator Summary

AgentAudit is the only compliance tool that assesses multi-agent harness architectures. Based on Anthropic's research on harness design for long-running apps:

| What competitors assess | What AgentAudit adds |
|---|---|
| Individual LLM calls | Inter-agent handoff logging |
| Single-agent traces | Harness topology detection (single / gen-eval / planner-gen-eval) |
| Basic human oversight checkboxes | Evaluator calibration as Article 14 evidence |
| Change management audit | Sprint contracts with per-criterion pass/fail |
| Log continuity | Context reset trace linking |
| Aggregate cost tracking | Per-agent-role cost and duration |
| Self-evaluation (biased) | Agent role separation verification |

This positions AgentAudit ahead of Airia, Credo AI, Norm AI, and all observability vendors — none of whom assess compliance at the orchestration layer where production AI systems actually operate.

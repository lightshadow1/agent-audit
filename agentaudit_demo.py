#!/usr/bin/env python3
"""
AgentAudit Demo — Single-script proof of concept.

Generates a EU AI Act Article 12 + SOC 2 compliance report from sample AI agent traces.
This is NOT the full product — it's a validation artifact to show compliance officers
and get feedback before building the real thing.

Usage:
    python agentaudit_demo.py

Output:
    agentaudit-compliance-report.pdf
    agentaudit-compliance-report.html
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 1. DATA MODELS
# ---------------------------------------------------------------------------

class EventType(str, Enum):
    NODE_EXECUTION = "node_execution"
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    CONDITIONAL_BRANCH = "conditional_branch"
    HUMAN_OVERSIGHT = "human_oversight"
    STATE_MUTATION = "state_mutation"
    ERROR = "error"
    SUBGRAPH_ENTRY = "subgraph_entry"
    SUBGRAPH_EXIT = "subgraph_exit"


@dataclass
class TraceEvent:
    event_id: str
    trace_id: str
    timestamp: datetime
    event_type: EventType
    node_name: str | None = None
    parent_event_id: str | None = None
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    duration_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    hash_prev: str | None = None
    hash_self: str | None = None


@dataclass
class Trace:
    trace_id: str
    agent_name: str
    timestamp_start: datetime
    timestamp_end: datetime | None
    status: str  # completed | failed
    events: list[TraceEvent] = field(default_factory=list)

    @property
    def total_llm_calls(self) -> int:
        return sum(1 for e in self.events if e.event_type == EventType.LLM_CALL)

    @property
    def total_tool_calls(self) -> int:
        return sum(1 for e in self.events if e.event_type == EventType.TOOL_CALL)

    @property
    def total_tokens(self) -> int:
        return sum(e.metadata.get("total_tokens", 0) for e in self.events if e.event_type == EventType.LLM_CALL)

    @property
    def estimated_cost(self) -> float:
        return sum(e.metadata.get("cost_usd", 0.0) for e in self.events if e.event_type == EventType.LLM_CALL)

    @property
    def has_human_oversight(self) -> bool:
        return any(e.event_type == EventType.HUMAN_OVERSIGHT for e in self.events)

    @property
    def has_errors(self) -> bool:
        return any(e.event_type == EventType.ERROR for e in self.events)

    @property
    def has_hash_chain(self) -> bool:
        return any(e.hash_prev is not None for e in self.events)


@dataclass
class ComplianceStatus:
    status: str  # met | partial | not_met | not_applicable
    confidence: float
    evidence_count: int
    evidence_sample: list[str]
    gap_description: str | None = None
    remediation: str | None = None


@dataclass
class Gap:
    framework: str
    requirement_id: str
    requirement_name: str
    article_or_code: str
    severity: str  # critical | warning
    current_state: str
    required_state: str
    remediation_steps: list[str]
    affected_traces: int
    total_traces: int


# ---------------------------------------------------------------------------
# 2. SAMPLE TRACE GENERATOR
# ---------------------------------------------------------------------------

def generate_sample_traces() -> list[Trace]:
    """
    Generate realistic sample traces that simulate what you'd pull from Langfuse.
    These represent a mix of compliant and non-compliant agent executions.
    """
    traces = []
    base_time = datetime.now(timezone.utc) - timedelta(days=90)

    for i in range(50):
        t_start = base_time + timedelta(days=i * 1.8, hours=i % 8)
        trace_id = f"tr-{i:04d}"
        events = []
        evt_idx = 0

        # -- Node execution: router
        events.append(TraceEvent(
            event_id=f"{trace_id}-evt-{evt_idx:03d}",
            trace_id=trace_id,
            timestamp=t_start,
            event_type=EventType.NODE_EXECUTION,
            node_name="router",
            input_data={"query": f"Sample query {i}"},
            output_data={"route": "research" if i % 3 != 0 else "direct_answer"},
            duration_ms=120.0,
            metadata={"component": "router_node", "agent_version": "1.2.0"},
        ))
        evt_idx += 1

        # -- LLM call inside router
        events.append(TraceEvent(
            event_id=f"{trace_id}-evt-{evt_idx:03d}",
            trace_id=trace_id,
            timestamp=t_start + timedelta(milliseconds=50),
            event_type=EventType.LLM_CALL,
            node_name="router",
            parent_event_id=events[0].event_id,
            input_data={"prompt": f"Classify this query: Sample query {i}"},
            output_data={"completion": "This requires research."},
            duration_ms=95.0,
            metadata={
                "model": "claude-sonnet-4-6",
                "input_tokens": 234,
                "output_tokens": 45,
                "total_tokens": 279,
                "cost_usd": 0.003,
                "component": "router_node",
            },
        ))
        evt_idx += 1

        # -- Conditional branch
        events.append(TraceEvent(
            event_id=f"{trace_id}-evt-{evt_idx:03d}",
            trace_id=trace_id,
            timestamp=t_start + timedelta(milliseconds=130),
            event_type=EventType.CONDITIONAL_BRANCH,
            node_name="router",
            input_data={"route": "research" if i % 3 != 0 else "direct_answer"},
            metadata={
                "branch_taken": "research" if i % 3 != 0 else "direct_answer",
                "condition": "query_complexity > 0.7",
                "component": "router_node",
            },
        ))
        evt_idx += 1

        # -- Tool call: web search
        if i % 3 != 0:
            events.append(TraceEvent(
                event_id=f"{trace_id}-evt-{evt_idx:03d}",
                trace_id=trace_id,
                timestamp=t_start + timedelta(milliseconds=200),
                event_type=EventType.TOOL_CALL,
                node_name="research_agent",
                input_data={"tool": "web_search", "query": f"AI observability trends {2026 - i % 5}"},
                output_data={"results": [{"title": f"Result {j}", "url": f"https://example.com/{j}"} for j in range(3)]},
                duration_ms=1200.0,
                metadata={"tool_name": "web_search", "success": True, "component": "research_node"},
            ))
            evt_idx += 1

        # -- Second LLM call: synthesis
        events.append(TraceEvent(
            event_id=f"{trace_id}-evt-{evt_idx:03d}",
            trace_id=trace_id,
            timestamp=t_start + timedelta(milliseconds=1500),
            event_type=EventType.LLM_CALL,
            node_name="synthesis_agent",
            parent_event_id=events[0].event_id,
            input_data={"prompt": "Synthesize the research findings..."},
            output_data={"completion": f"Based on the analysis, the key findings are... (trace {i})"},
            duration_ms=2100.0,
            metadata={
                "model": "claude-sonnet-4-6",
                "input_tokens": 1890,
                "output_tokens": 567,
                "total_tokens": 2457,
                "cost_usd": 0.024,
                "component": "synthesis_node",
            },
        ))
        evt_idx += 1

        # -- State mutation
        events.append(TraceEvent(
            event_id=f"{trace_id}-evt-{evt_idx:03d}",
            trace_id=trace_id,
            timestamp=t_start + timedelta(milliseconds=3700),
            event_type=EventType.STATE_MUTATION,
            node_name="synthesis_agent",
            metadata={
                "changed_keys": ["research_results", "confidence_score"],
                "confidence_score": 0.82 + (i % 10) * 0.015,
                "component": "synthesis_node",
            },
        ))
        evt_idx += 1

        # -- Human oversight (only ~30% of traces — this creates a gap)
        if i % 10 < 3:
            events.append(TraceEvent(
                event_id=f"{trace_id}-evt-{evt_idx:03d}",
                trace_id=trace_id,
                timestamp=t_start + timedelta(milliseconds=4000),
                event_type=EventType.HUMAN_OVERSIGHT,
                node_name="review_gate",
                input_data={"action": "approve_output"},
                output_data={"decision": "approved", "reviewer": f"reviewer_{i % 5}"},
                metadata={"reviewer_id": f"user-{i % 5:03d}", "component": "review_gate"},
            ))
            evt_idx += 1

        # -- Error events (in ~10% of traces)
        if i % 10 == 7:
            events.append(TraceEvent(
                event_id=f"{trace_id}-evt-{evt_idx:03d}",
                trace_id=trace_id,
                timestamp=t_start + timedelta(milliseconds=3800),
                event_type=EventType.ERROR,
                node_name="synthesis_agent",
                metadata={
                    "error_code": "CONTEXT_OVERFLOW",
                    "error_message": "Context window exceeded. Truncating input.",
                    "severity": "warning",
                    "impact": "degraded_output",
                    "component": "synthesis_node",
                    "traceback": "File 'agent.py', line 142, in synthesize\n  ...",
                },
            ))
            evt_idx += 1

        # -- Hash chain (only ~60% of traces have it — another gap)
        if i % 5 < 3:
            prev_hash = "sha256:0000000000000000"
            for evt in events:
                evt.hash_prev = prev_hash
                canonical = json.dumps(
                    {k: str(v) for k, v in {"id": evt.event_id, "type": evt.event_type.value, "ts": str(evt.timestamp)}.items()},
                    sort_keys=True
                )
                evt.hash_self = f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()[:16]}"
                prev_hash = evt.hash_self

        t_end = t_start + timedelta(milliseconds=4500 + (i % 20) * 100)
        traces.append(Trace(
            trace_id=trace_id,
            agent_name="research_writer_agent",
            timestamp_start=t_start,
            timestamp_end=t_end,
            status="failed" if i % 10 == 7 else "completed",
            events=events,
        ))

    return traces


# ---------------------------------------------------------------------------
# 3. COMPLIANCE ASSESSMENT ENGINE
# ---------------------------------------------------------------------------

def assess_article12(traces: list[Trace]) -> dict[str, ComplianceStatus]:
    """Assess traces against EU AI Act Article 12 + connected articles."""
    n = len(traces)
    results = {}

    # --- Art 12(1): Automatic logging ---
    traces_with_events = sum(1 for t in traces if len(t.events) > 0)
    pct = traces_with_events / n if n > 0 else 0
    results["art12_automatic_logging"] = ComplianceStatus(
        status="met" if pct > 0.95 else "partial" if pct > 0.5 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=traces_with_events,
        evidence_sample=[t.trace_id for t in traces[:5] if t.events],
    )

    # --- Art 12(2)(a): Risk identification ---
    traces_with_errors = sum(1 for t in traces if t.has_errors)
    has_severity = sum(1 for t in traces for e in t.events if e.event_type == EventType.ERROR and "severity" in e.metadata)
    results["art12_risk_identification"] = ComplianceStatus(
        status="met" if traces_with_errors > 0 and has_severity > 0 else "partial" if traces_with_errors > 0 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=traces_with_errors,
        evidence_sample=[t.trace_id for t in traces if t.has_errors][:5],
        gap_description=None if traces_with_errors > 0 else "No error events captured in any trace",
        remediation="Ensure all exceptions and anomalies are logged with severity levels" if traces_with_errors == 0 else None,
    )

    # --- Art 12(2)(b): Post-market monitoring ---
    event_types_present = set()
    for t in traces:
        for e in t.events:
            event_types_present.add(e.event_type)
    required_types = {EventType.NODE_EXECUTION, EventType.LLM_CALL, EventType.TOOL_CALL, EventType.ERROR}
    coverage = len(event_types_present & required_types) / len(required_types)
    results["art12_post_market_monitoring"] = ComplianceStatus(
        status="met" if coverage >= 0.75 else "partial" if coverage >= 0.5 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=len(event_types_present),
        evidence_sample=[et.value for et in event_types_present],
    )

    # --- Art 12(2)(c): Operational monitoring ---
    traces_with_status = sum(1 for t in traces if t.status in ("completed", "failed"))
    pct = traces_with_status / n if n > 0 else 0
    results["art12_operational_monitoring"] = ComplianceStatus(
        status="met" if pct > 0.95 else "partial" if pct > 0.5 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=traces_with_status,
        evidence_sample=[t.trace_id for t in traces[:5]],
    )

    # --- Art 12(3)(a): Session timestamps ---
    traces_with_timestamps = sum(1 for t in traces if t.timestamp_start and t.timestamp_end)
    pct = traces_with_timestamps / n if n > 0 else 0
    results["art12_session_timestamps"] = ComplianceStatus(
        status="met" if pct > 0.95 else "partial" if pct > 0.5 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=traces_with_timestamps,
        evidence_sample=[t.trace_id for t in traces[:5] if t.timestamp_start and t.timestamp_end],
    )

    # --- Art 12(3)(c): Input recording ---
    events_with_input = sum(1 for t in traces for e in t.events if e.input_data)
    total_events = sum(len(t.events) for t in traces)
    pct = events_with_input / total_events if total_events > 0 else 0
    results["art12_input_recording"] = ComplianceStatus(
        status="met" if pct > 0.8 else "partial" if pct > 0.4 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=events_with_input,
        evidence_sample=[],
    )

    # --- Art 14: Human oversight ---
    traces_with_oversight = sum(1 for t in traces if t.has_human_oversight)
    pct = traces_with_oversight / n if n > 0 else 0
    results["art14_human_oversight"] = ComplianceStatus(
        status="met" if pct > 0.8 else "partial" if pct > 0.1 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=traces_with_oversight,
        evidence_sample=[t.trace_id for t in traces if t.has_human_oversight][:5],
        gap_description=f"Only {traces_with_oversight} of {n} traces ({pct:.0%}) contain human oversight events. Article 14 requires logging of human intervention points for high-risk AI systems.",
        remediation="Add human-in-the-loop checkpoints to your agent workflow. In LangGraph, use interrupt_before/interrupt_after on critical decision nodes. Configure your observability tool to capture these events.",
    )

    # --- Art 26: Log retention (6 months) ---
    if traces:
        earliest = min(t.timestamp_start for t in traces)
        latest = max(t.timestamp_start for t in traces)
        span_days = (latest - earliest).days
    else:
        span_days = 0
    results["art26_log_retention"] = ComplianceStatus(
        status="met" if span_days >= 180 else "partial" if span_days >= 90 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=span_days,
        evidence_sample=[],
        gap_description=f"Trace data spans {span_days} days. Article 26 requires minimum 6 months (180 days) of log retention." if span_days < 180 else None,
        remediation="Configure your observability tool to retain trace data for at least 6 months. Check Langfuse/Laminar retention settings." if span_days < 180 else None,
    )

    # --- Art 72/79: Incident support ---
    error_events_with_context = sum(
        1 for t in traces for e in t.events
        if e.event_type == EventType.ERROR and all(k in e.metadata for k in ("error_code", "severity"))
    )
    results["art72_incident_support"] = ComplianceStatus(
        status="met" if error_events_with_context > 0 else "partial" if traces_with_errors > 0 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=error_events_with_context,
        evidence_sample=[],
    )

    # --- EN 18229-1: Component identification ---
    events_with_component = sum(1 for t in traces for e in t.events if e.node_name or e.metadata.get("component"))
    pct = events_with_component / total_events if total_events > 0 else 0
    results["en_component_identification"] = ComplianceStatus(
        status="met" if pct > 0.9 else "partial" if pct > 0.5 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=events_with_component,
        evidence_sample=[],
    )

    # --- EN 18229-1: Timestamp completeness ---
    events_with_ts = sum(1 for t in traces for e in t.events if e.timestamp)
    pct = events_with_ts / total_events if total_events > 0 else 0
    results["en_timestamp_completeness"] = ComplianceStatus(
        status="met" if pct > 0.99 else "partial" if pct > 0.8 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=events_with_ts,
        evidence_sample=[],
    )

    # --- Tamper evidence: Hash chain ---
    traces_with_chain = sum(1 for t in traces if t.has_hash_chain)
    pct = traces_with_chain / n if n > 0 else 0
    results["tamper_evidence"] = ComplianceStatus(
        status="met" if pct > 0.9 else "partial" if pct > 0.3 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=traces_with_chain,
        evidence_sample=[t.trace_id for t in traces if t.has_hash_chain][:5],
        gap_description=f"Only {traces_with_chain} of {n} traces ({pct:.0%}) have hash-chain integrity verification." if pct < 0.9 else None,
        remediation="Enable tamper-evident logging in your observability tool, or add AgentAudit's hash-chain wrapper to your trace pipeline." if pct < 0.9 else None,
    )

    return results


def assess_soc2(traces: list[Trace]) -> dict[str, ComplianceStatus]:
    """Assess traces against relevant SOC 2 CC criteria."""
    n = len(traces)
    total_events = sum(len(t.events) for t in traces)
    results = {}

    # --- CC7.1: Anomaly detection ---
    traces_with_errors = sum(1 for t in traces if t.has_errors)
    results["cc7_1"] = ComplianceStatus(
        status="met" if traces_with_errors > 0 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=traces_with_errors,
        evidence_sample=[t.trace_id for t in traces if t.has_errors][:5],
        gap_description="No anomaly or error detection events in traces" if traces_with_errors == 0 else None,
    )

    # --- CC7.2: Failure monitoring ---
    error_events = sum(1 for t in traces for e in t.events if e.event_type == EventType.ERROR)
    results["cc7_2"] = ComplianceStatus(
        status="met" if error_events > 0 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=error_events,
        evidence_sample=[],
    )

    # --- CC7.3: Event triage ---
    events_with_severity = sum(
        1 for t in traces for e in t.events
        if e.event_type == EventType.ERROR and "severity" in e.metadata
    )
    results["cc7_3"] = ComplianceStatus(
        status="met" if events_with_severity > 0 else "partial" if error_events > 0 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=events_with_severity,
        evidence_sample=[],
        gap_description="Error events lack severity classification" if error_events > 0 and events_with_severity == 0 else None,
    )

    # --- CC7.5: Root cause analysis ---
    events_with_traceback = sum(
        1 for t in traces for e in t.events
        if e.event_type == EventType.ERROR and "traceback" in e.metadata
    )
    results["cc7_5"] = ComplianceStatus(
        status="met" if events_with_traceback > 0 else "partial" if error_events > 0 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=events_with_traceback,
        evidence_sample=[],
    )

    # --- CC5.3: Human oversight policies deployed ---
    traces_with_oversight = sum(1 for t in traces if t.has_human_oversight)
    pct = traces_with_oversight / n if n > 0 else 0
    results["cc5_3"] = ComplianceStatus(
        status="met" if pct > 0.8 else "partial" if pct > 0.1 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=traces_with_oversight,
        evidence_sample=[t.trace_id for t in traces if t.has_human_oversight][:5],
        gap_description=f"Human oversight policies evidenced in only {pct:.0%} of traces" if pct < 0.8 else None,
    )

    # --- CC8.1: Change management (model/agent version logging) ---
    events_with_version = sum(
        1 for t in traces for e in t.events if "agent_version" in e.metadata or "model" in e.metadata
    )
    pct = events_with_version / total_events if total_events > 0 else 0
    results["cc8_1"] = ComplianceStatus(
        status="met" if pct > 0.5 else "partial" if pct > 0.1 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=events_with_version,
        evidence_sample=[],
    )

    # --- CC2.3: Third-party communication (external API calls logged) ---
    tool_calls = sum(1 for t in traces for e in t.events if e.event_type == EventType.TOOL_CALL)
    results["cc2_3"] = ComplianceStatus(
        status="met" if tool_calls > 0 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=tool_calls,
        evidence_sample=[],
    )

    # --- PI1.3: Input completeness ---
    events_with_input = sum(1 for t in traces for e in t.events if e.input_data)
    pct = events_with_input / total_events if total_events > 0 else 0
    results["pi1_3"] = ComplianceStatus(
        status="met" if pct > 0.8 else "partial" if pct > 0.4 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=events_with_input,
        evidence_sample=[],
    )

    # --- PI1.4: Output completeness ---
    events_with_output = sum(1 for t in traces for e in t.events if e.output_data)
    pct = events_with_output / total_events if total_events > 0 else 0
    results["pi1_4"] = ComplianceStatus(
        status="met" if pct > 0.7 else "partial" if pct > 0.3 else "not_met",
        confidence=min(n / 100, 1.0),
        evidence_count=events_with_output,
        evidence_sample=[],
    )

    return results


# ---------------------------------------------------------------------------
# 4. GAP ANALYSIS
# ---------------------------------------------------------------------------

ARTICLE12_NAMES = {
    "art12_automatic_logging": ("Automatic Recording of Events", "Art. 12(1)"),
    "art12_risk_identification": ("Risk Event Recording", "Art. 12(2)(a)"),
    "art12_post_market_monitoring": ("Post-Market Monitoring Support", "Art. 12(2)(b)"),
    "art12_operational_monitoring": ("Operational Monitoring", "Art. 12(2)(c)"),
    "art12_session_timestamps": ("Session Timestamps", "Art. 12(3)(a)"),
    "art12_input_recording": ("Input Data Recording", "Art. 12(3)(c)"),
    "art14_human_oversight": ("Human Oversight Logging", "Art. 14"),
    "art26_log_retention": ("Log Retention (6 months)", "Art. 26"),
    "art72_incident_support": ("Incident Reporting Support", "Art. 72/79"),
    "en_component_identification": ("Component Identification", "EN 18229-1"),
    "en_timestamp_completeness": ("Timestamp Completeness", "EN 18229-1"),
    "tamper_evidence": ("Tamper Evidence / Log Integrity", "Implied / EN 18229-1"),
}

SOC2_NAMES = {
    "cc7_1": ("Anomaly Detection & Monitoring", "CC7.1"),
    "cc7_2": ("Failure Monitoring", "CC7.2"),
    "cc7_3": ("Event Triage & Severity Classification", "CC7.3"),
    "cc7_5": ("Root Cause Analysis Support", "CC7.5"),
    "cc5_3": ("Human Oversight Policies Deployed", "CC5.3"),
    "cc8_1": ("Change Management (Version Logging)", "CC8.1"),
    "cc2_3": ("Third-Party Communication Logging", "CC2.3"),
    "pi1_3": ("Input Completeness", "PI1.3"),
    "pi1_4": ("Output Completeness", "PI1.4"),
}

REMEDIATION_MAP = {
    "art14_human_oversight": [
        "Add human-in-the-loop checkpoints to your LangGraph agent using interrupt_before/interrupt_after",
        "In Langfuse: use trace.event(name='human_oversight', metadata={reviewer_id: ..., decision: ...})",
        "In Laminar: add @observe decorator on approval/review functions",
        "Ensure every high-risk decision path includes a human review gate",
    ],
    "art26_log_retention": [
        "Configure your observability tool to retain data for at least 6 months",
        "Langfuse Cloud: check your plan's retention limits",
        "Self-hosted: configure database retention policies",
        "For financial services: align with your existing record-keeping obligations",
    ],
    "tamper_evidence": [
        "Enable hash-chain logging if your observability tool supports it",
        "Alternatively, export traces to an append-only store (e.g., S3 with Object Lock)",
        "Consider adding cryptographic signatures to trace batches",
    ],
    "cc5_3": [
        "Same as Article 14: add human oversight checkpoints and log them",
        "Document your human oversight policy and reference it in trace metadata",
    ],
}


def analyze_gaps(
    art12_results: dict[str, ComplianceStatus],
    soc2_results: dict[str, ComplianceStatus],
    total_traces: int,
) -> list[Gap]:
    """Identify all compliance gaps with remediation."""
    gaps = []

    for req_id, status in art12_results.items():
        if status.status in ("partial", "not_met"):
            name, article = ARTICLE12_NAMES.get(req_id, (req_id, ""))
            gaps.append(Gap(
                framework="EU AI Act",
                requirement_id=req_id,
                requirement_name=name,
                article_or_code=article,
                severity="critical" if status.status == "not_met" else "warning",
                current_state=status.gap_description or f"Status: {status.status} ({status.evidence_count} evidence items)",
                required_state=f"Article {article} compliance requires this to be fully met",
                remediation_steps=REMEDIATION_MAP.get(req_id, [status.remediation or "Review and address this requirement"]),
                affected_traces=total_traces - status.evidence_count,
                total_traces=total_traces,
            ))

    for req_id, status in soc2_results.items():
        if status.status in ("partial", "not_met"):
            name, code = SOC2_NAMES.get(req_id, (req_id, ""))
            gaps.append(Gap(
                framework="SOC 2",
                requirement_id=req_id,
                requirement_name=name,
                article_or_code=code,
                severity="critical" if status.status == "not_met" else "warning",
                current_state=status.gap_description or f"Status: {status.status} ({status.evidence_count} evidence items)",
                required_state=f"SOC 2 {code} requires this control to be evidenced",
                remediation_steps=REMEDIATION_MAP.get(req_id, [status.remediation or "Review and address this criterion"]),
                affected_traces=total_traces - status.evidence_count,
                total_traces=total_traces,
            ))

    # Sort: critical first, then by framework
    gaps.sort(key=lambda g: (0 if g.severity == "critical" else 1, g.framework, g.requirement_id))
    return gaps


def calc_score(results: dict[str, ComplianceStatus]) -> float:
    """Calculate compliance percentage (met = 1.0, partial = 0.5, not_met = 0)."""
    if not results:
        return 0.0
    score = sum(1.0 if s.status == "met" else 0.5 if s.status == "partial" else 0.0 for s in results.values())
    return round(score / len(results) * 100, 1)


# ---------------------------------------------------------------------------
# 5. REPORT GENERATORS
# ---------------------------------------------------------------------------

def generate_pdf_report(
    traces: list[Trace],
    art12: dict[str, ComplianceStatus],
    soc2: dict[str, ComplianceStatus],
    gaps: list[Gap],
    output_path: str,
):
    """Generate a professional PDF compliance report."""
    from fpdf import FPDF

    class Report(FPDF):
        def header(self):
            if self.page_no() > 1:
                self.set_font("Helvetica", "I", 8)
                self.set_text_color(128, 128, 128)
                self.cell(0, 10, "AgentAudit Compliance Assessment", align="L")
                self.cell(0, 10, f"Page {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")
                self.line(10, 18, 200, 18)
                self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(160, 160, 160)
            self.cell(0, 10, f"Generated by AgentAudit v0.1.0 | {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}", align="C")

    pdf = Report()
    pdf.set_auto_page_break(auto=True, margin=20)

    # --- COVER PAGE ---
    pdf.add_page()
    pdf.ln(60)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 15, "AI Agent Compliance", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 15, "Assessment Report", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 10, "EU AI Act Article 12 + SOC 2 Trust Service Criteria", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)
    pdf.set_font("Helvetica", "", 11)

    earliest = min(t.timestamp_start for t in traces)
    latest = max(t.timestamp_start for t in traces)
    total_events = sum(len(t.events) for t in traces)

    cover_info = [
        ("Assessment Period", f"{earliest.strftime('%B %d, %Y')} - {latest.strftime('%B %d, %Y')}"),
        ("Report Generated", datetime.now().strftime("%B %d, %Y")),
        ("Data Source", "Agent Observability Platform"),
        ("Traces Analyzed", str(len(traces))),
        ("Total Events", f"{total_events:,}"),
        ("Agent", traces[0].agent_name if traces else "N/A"),
    ]
    for label, value in cover_info:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(60, 8, label + ":", new_x="END")
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 8, value, new_x="LMARGIN", new_y="NEXT")

    # --- EXECUTIVE SUMMARY ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 12, "Executive Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    art12_score = calc_score(art12)
    soc2_score = calc_score(soc2)
    critical_gaps = sum(1 for g in gaps if g.severity == "critical")
    warnings = sum(1 for g in gaps if g.severity == "warning")
    met_count = sum(1 for s in list(art12.values()) + list(soc2.values()) if s.status == "met")
    total_reqs = len(art12) + len(soc2)

    # Score boxes
    pdf.set_font("Helvetica", "B", 12)
    for label, score in [("EU AI Act Article 12", art12_score), ("SOC 2 Trust Service Criteria", soc2_score)]:
        if score >= 80:
            pdf.set_fill_color(220, 250, 220)
        elif score >= 50:
            pdf.set_fill_color(255, 250, 220)
        else:
            pdf.set_fill_color(255, 220, 220)
        pdf.cell(90, 12, f"  {label}: {score}%", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    pdf.ln(5)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_fill_color(255, 255, 255)

    summary_lines = [
        f"This assessment analyzed {len(traces)} agent traces containing {total_events:,} events over a {(latest - earliest).days}-day period.",
        f"Of {total_reqs} total compliance requirements assessed, {met_count} are fully met, {total_reqs - met_count - critical_gaps} are partially met, and {critical_gaps} have critical gaps.",
        f"There are {critical_gaps} critical gaps requiring immediate remediation and {warnings} warnings to address.",
    ]
    for line in summary_lines:
        pdf.multi_cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    # --- ARTICLE 12 DETAILED ASSESSMENT ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "EU AI Act Article 12 Assessment", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Table header
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(240, 240, 240)
    col_widths = [55, 20, 14, 100]
    headers_text = ["Requirement", "Article", "Status", "Evidence / Gap"]
    for w, h_text in zip(col_widths, headers_text):
        pdf.cell(w, 8, h_text, border=1, fill=True, new_x="END")
    pdf.ln()

    pdf.set_font("Helvetica", "", 7.5)
    for req_id, status in art12.items():
        name, article = ARTICLE12_NAMES.get(req_id, (req_id, ""))
        symbol = "MET" if status.status == "met" else "PARTIAL" if status.status == "partial" else "GAP"
        detail = status.gap_description or f"Evidence: {status.evidence_count} items"
        if len(detail) > 130:
            detail = detail[:127] + "..."

        y_before = pdf.get_y()
        if y_before > 260:
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_fill_color(240, 240, 240)
            for w, h_text in zip(col_widths, headers_text):
                pdf.cell(w, 8, h_text, border=1, fill=True, new_x="END")
            pdf.ln()
            pdf.set_font("Helvetica", "", 7.5)

        pdf.cell(col_widths[0], 7, name[:35], border=1, new_x="END")
        pdf.cell(col_widths[1], 7, article, border=1, new_x="END")

        if status.status == "met":
            pdf.set_text_color(0, 128, 0)
        elif status.status == "partial":
            pdf.set_text_color(200, 150, 0)
        else:
            pdf.set_text_color(200, 0, 0)
        pdf.cell(col_widths[2], 7, symbol, border=1, align="C", new_x="END")
        pdf.set_text_color(30, 30, 30)

        pdf.cell(col_widths[3], 7, detail[:85], border=1, new_x="LMARGIN", new_y="NEXT")

    # --- SOC 2 DETAILED ASSESSMENT ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "SOC 2 Trust Service Criteria Assessment", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(240, 240, 240)
    col_widths2 = [55, 20, 14, 100]
    headers2 = ["Requirement", "CC Code", "Status", "Evidence / Gap"]
    for w, h_text in zip(col_widths2, headers2):
        pdf.cell(w, 8, h_text, border=1, fill=True, new_x="END")
    pdf.ln()

    pdf.set_font("Helvetica", "", 7.5)
    for req_id, status in soc2.items():
        name, code = SOC2_NAMES.get(req_id, (req_id, ""))
        symbol = "MET" if status.status == "met" else "PARTIAL" if status.status == "partial" else "GAP"
        detail = status.gap_description or f"Evidence: {status.evidence_count} items"

        pdf.cell(col_widths2[0], 7, name[:35], border=1, new_x="END")
        pdf.cell(col_widths2[1], 7, code, border=1, new_x="END")

        if status.status == "met":
            pdf.set_text_color(0, 128, 0)
        elif status.status == "partial":
            pdf.set_text_color(200, 150, 0)
        else:
            pdf.set_text_color(200, 0, 0)
        pdf.cell(col_widths2[2], 7, symbol, border=1, align="C", new_x="END")
        pdf.set_text_color(30, 30, 30)

        pdf.cell(col_widths2[3], 7, detail[:85], border=1, new_x="LMARGIN", new_y="NEXT")

    # --- GAP ANALYSIS ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "Gap Analysis & Remediation Plan", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    for i, gap in enumerate(gaps):
        if pdf.get_y() > 240:
            pdf.add_page()

        # Gap header
        if gap.severity == "critical":
            pdf.set_fill_color(255, 220, 220)
            label = "CRITICAL"
        else:
            pdf.set_fill_color(255, 250, 220)
            label = "WARNING"

        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 8, f"  [{label}] {gap.requirement_name} ({gap.article_or_code}) - {gap.framework}",
                 fill=True, new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "", 8)
        pdf.set_fill_color(255, 255, 255)

        pdf.ln(1)
        current = gap.current_state
        if len(current) > 200:
            current = current[:197] + "..."
        pdf.multi_cell(0, 5, f"Current: {current}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(0, 5, "Remediation:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 8)
        for step in gap.remediation_steps[:4]:
            if pdf.get_y() > 270:
                pdf.add_page()
            step_text = step if len(step) <= 120 else step[:117] + "..."
            pdf.cell(0, 5, f"  - {step_text}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # --- METHODOLOGY ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "Methodology", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 9)
    methodology = [
        f"Data Source: Agent observability trace data",
        f"Assessment Period: {earliest.strftime('%Y-%m-%d')} to {latest.strftime('%Y-%m-%d')} ({(latest - earliest).days} days)",
        f"Traces Analyzed: {len(traces)}",
        f"Events Analyzed: {total_events:,}",
        f"EU AI Act Requirements Assessed: {len(art12)} (Article 12 + connected articles)",
        f"SOC 2 Criteria Assessed: {len(soc2)} (selected CC + additional criteria)",
        f"Assessment Rules: AgentAudit v0.1.0 rule set",
        f"",
        f"Confidence Level: {'High' if len(traces) >= 100 else 'Medium' if len(traces) >= 30 else 'Low'} (based on {len(traces)} traces)",
        f"",
        f"This report was generated automatically by AgentAudit. The compliance assessment is based on",
        f"analysis of agent trace data and should be reviewed by qualified legal and compliance professionals.",
        f"This report does not constitute legal advice.",
    ]
    for line in methodology:
        pdf.cell(0, 5, line, new_x="LMARGIN", new_y="NEXT")

    pdf.output(output_path)


def generate_html_report(
    traces: list[Trace],
    art12: dict[str, ComplianceStatus],
    soc2: dict[str, ComplianceStatus],
    gaps: list[Gap],
    output_path: str,
):
    """Generate an interactive HTML compliance report."""
    art12_score = calc_score(art12)
    soc2_score = calc_score(soc2)
    critical_gaps = sum(1 for g in gaps if g.severity == "critical")
    warnings = sum(1 for g in gaps if g.severity == "warning")
    total_events = sum(len(t.events) for t in traces)
    earliest = min(t.timestamp_start for t in traces)
    latest = max(t.timestamp_start for t in traces)
    met_count = sum(1 for s in list(art12.values()) + list(soc2.values()) if s.status == "met")
    total_reqs = len(art12) + len(soc2)

    def status_badge(s: str) -> str:
        colors = {"met": "#16a34a", "partial": "#ca8a04", "not_met": "#dc2626"}
        labels = {"met": "MET", "partial": "PARTIAL", "not_met": "GAP"}
        c = colors.get(s, "#666")
        return f'<span style="background:{c};color:white;padding:2px 8px;border-radius:3px;font-size:12px;font-weight:600">{labels.get(s, s.upper())}</span>'

    def score_color(score: float) -> str:
        if score >= 80: return "#16a34a"
        if score >= 50: return "#ca8a04"
        return "#dc2626"

    art12_rows = ""
    for req_id, status in art12.items():
        name, article = ARTICLE12_NAMES.get(req_id, (req_id, ""))
        detail = status.gap_description or f"Evidence: {status.evidence_count} items"
        art12_rows += f"""<tr>
            <td>{name}</td><td>{article}</td><td>{status_badge(status.status)}</td>
            <td style="font-size:13px">{detail}</td></tr>\n"""

    soc2_rows = ""
    for req_id, status in soc2.items():
        name, code = SOC2_NAMES.get(req_id, (req_id, ""))
        detail = status.gap_description or f"Evidence: {status.evidence_count} items"
        soc2_rows += f"""<tr>
            <td>{name}</td><td>{code}</td><td>{status_badge(status.status)}</td>
            <td style="font-size:13px">{detail}</td></tr>\n"""

    gap_html = ""
    for gap in gaps:
        bg = "#fef2f2" if gap.severity == "critical" else "#fefce8"
        border = "#fca5a5" if gap.severity == "critical" else "#fde68a"
        label_bg = "#dc2626" if gap.severity == "critical" else "#ca8a04"
        steps = "".join(f"<li>{s}</li>" for s in gap.remediation_steps[:4])
        gap_html += f"""
        <div style="background:{bg};border:1px solid {border};border-radius:8px;padding:16px;margin-bottom:12px">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
                <span style="background:{label_bg};color:white;padding:2px 8px;border-radius:3px;font-size:11px;font-weight:700">{gap.severity.upper()}</span>
                <strong>{gap.requirement_name}</strong>
                <span style="color:#666;font-size:13px">({gap.article_or_code} - {gap.framework})</span>
            </div>
            <p style="margin:4px 0;font-size:13px;color:#444">{gap.current_state}</p>
            <details><summary style="cursor:pointer;font-weight:600;font-size:13px;margin-top:8px">Remediation Steps</summary>
            <ul style="font-size:13px;margin-top:4px">{steps}</ul></details>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Agent Compliance Assessment Report</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #1a1a1a; max-width: 960px; margin: 0 auto; padding: 40px 20px; line-height: 1.6; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #111; color: #e0e0e0; }}
    table {{ border-color: #333; }}
    th {{ background: #222 !important; }}
    td {{ border-color: #333; }}
  }}
  h1 {{ font-size: 28px; margin-bottom: 4px; }}
  h2 {{ font-size: 20px; margin: 32px 0 16px; padding-bottom: 8px; border-bottom: 2px solid #e5e7eb; }}
  .meta {{ color: #666; font-size: 14px; margin-bottom: 24px; }}
  .scores {{ display: flex; gap: 16px; margin: 24px 0; }}
  .score-box {{ flex: 1; padding: 20px; border-radius: 8px; text-align: center; }}
  .score-box .value {{ font-size: 36px; font-weight: 700; }}
  .score-box .label {{ font-size: 13px; color: #666; margin-top: 4px; }}
  .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 16px 0 24px; }}
  .stat {{ background: #f9fafb; padding: 12px; border-radius: 6px; text-align: center; }}
  .stat .num {{ font-size: 24px; font-weight: 700; }}
  .stat .lbl {{ font-size: 12px; color: #666; }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 14px; }}
  th {{ background: #f3f4f6; text-align: left; padding: 10px; font-size: 13px; }}
  td {{ padding: 10px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }}
  .methodology {{ font-size: 13px; color: #666; margin-top: 32px; padding: 16px; background: #f9fafb; border-radius: 8px; }}
  @media print {{ body {{ max-width: none; padding: 20px; }} .scores {{ gap: 8px; }} }}
</style>
</head>
<body>
<h1>AI Agent Compliance Assessment</h1>
<p class="meta">EU AI Act Article 12 + SOC 2 Trust Service Criteria<br>
Assessment period: {earliest.strftime('%B %d, %Y')} - {latest.strftime('%B %d, %Y')} | Generated: {datetime.now().strftime('%B %d, %Y')}</p>

<div class="scores">
  <div class="score-box" style="background:{score_color(art12_score)}15;border:2px solid {score_color(art12_score)}">
    <div class="value" style="color:{score_color(art12_score)}">{art12_score}%</div>
    <div class="label">EU AI Act Article 12</div>
  </div>
  <div class="score-box" style="background:{score_color(soc2_score)}15;border:2px solid {score_color(soc2_score)}">
    <div class="value" style="color:{score_color(soc2_score)}">{soc2_score}%</div>
    <div class="label">SOC 2 Criteria</div>
  </div>
</div>

<div class="stats">
  <div class="stat"><div class="num">{len(traces)}</div><div class="lbl">Traces Analyzed</div></div>
  <div class="stat"><div class="num">{total_events:,}</div><div class="lbl">Total Events</div></div>
  <div class="stat"><div class="num" style="color:#dc2626">{critical_gaps}</div><div class="lbl">Critical Gaps</div></div>
  <div class="stat"><div class="num">{met_count}/{total_reqs}</div><div class="lbl">Requirements Met</div></div>
</div>

<h2>EU AI Act Article 12 Assessment</h2>
<table><tr><th>Requirement</th><th>Article</th><th>Status</th><th>Evidence / Gap</th></tr>
{art12_rows}</table>

<h2>SOC 2 Trust Service Criteria Assessment</h2>
<table><tr><th>Requirement</th><th>CC Code</th><th>Status</th><th>Evidence / Gap</th></tr>
{soc2_rows}</table>

<h2>Gap Analysis & Remediation Plan</h2>
{gap_html if gap_html else '<p style="color:#16a34a;font-weight:600">No gaps identified. All requirements are fully met.</p>'}

<div class="methodology">
  <strong>Methodology</strong><br>
  Data source: Agent observability trace data | Traces: {len(traces)} | Events: {total_events:,} | Period: {(latest - earliest).days} days<br>
  Frameworks: EU AI Act Article 12 ({len(art12)} requirements) + SOC 2 ({len(soc2)} criteria) | Confidence: {'High' if len(traces) >= 100 else 'Medium'}<br>
  Generated by AgentAudit v0.1.0. This report does not constitute legal advice.
</div>
</body>
</html>"""

    Path(output_path).write_text(html)


# ---------------------------------------------------------------------------
# 6. MAIN
# ---------------------------------------------------------------------------

def main():
    print("AgentAudit Demo - Compliance Report Generator")
    print("=" * 50)

    # Generate sample traces
    print("\n[1/4] Generating sample agent traces...")
    traces = generate_sample_traces()
    total_events = sum(len(t.events) for t in traces)
    print(f"  Created {len(traces)} traces with {total_events:,} events")

    # Run compliance assessment
    print("\n[2/4] Running compliance assessment...")
    art12_results = assess_article12(traces)
    soc2_results = assess_soc2(traces)
    art12_score = calc_score(art12_results)
    soc2_score = calc_score(soc2_results)
    print(f"  Article 12 Score: {art12_score}%")
    print(f"  SOC 2 Score:      {soc2_score}%")

    # Gap analysis
    print("\n[3/4] Analyzing gaps...")
    gaps = analyze_gaps(art12_results, soc2_results, len(traces))
    critical = sum(1 for g in gaps if g.severity == "critical")
    warnings = sum(1 for g in gaps if g.severity == "warning")
    print(f"  Found {critical} critical gaps, {warnings} warnings")

    for gap in gaps:
        icon = "!!" if gap.severity == "critical" else "  "
        print(f"  {icon} [{gap.severity.upper():8s}] {gap.requirement_name} ({gap.article_or_code})")

    # Generate reports
    print("\n[4/4] Generating reports...")

    output_dir = os.environ.get("OUTPUT_DIR", ".")
    pdf_path = os.path.join(output_dir, "agentaudit-compliance-report.pdf")
    html_path = os.path.join(output_dir, "agentaudit-compliance-report.html")

    generate_pdf_report(traces, art12_results, soc2_results, gaps, pdf_path)
    print(f"  PDF:  {pdf_path}")

    generate_html_report(traces, art12_results, soc2_results, gaps, html_path)
    print(f"  HTML: {html_path}")

    print("\nDone. Share these reports with compliance officers for feedback.")


if __name__ == "__main__":
    main()

"""Tests covering the second example agent's fixture.

Where otel_pass.jsonl is the well-instrumented baseline and otel_fail.jsonl
is a synthetically mutated version, otel_under_instrumented.jsonl is what a
real but partial OTel instrumentation produces. These tests pin the expected
gap pattern so it stays meaningful as the assessment logic evolves.
"""

from __future__ import annotations

from pathlib import Path

from agentaudit.adapters.otel import load
from agentaudit.article12 import assess
from agentaudit.models import CheckStatus, SpanKind

FIXTURE = Path(__file__).parent / "fixtures" / "otel_under_instrumented.jsonl"


def test_fixture_has_only_llm_spans() -> None:
    """The under-instrumented agent emits ONLY LLM spans — no agent root,
    no oversight. This is the realistic gap pattern."""
    traces = load(FIXTURE)
    assert traces, "fixture must contain at least one trace"
    for t in traces:
        kinds = {s.kind for s in t.spans}
        assert kinds == {SpanKind.llm}, (
            f"trace {t.trace_id} should have only llm spans, has {kinds}"
        )


def test_assessment_surfaces_expected_gaps() -> None:
    results = {
        r.check_id: r
        for r in assess(load(FIXTURE), retention_days=365)
    }

    # No agent-root spans → auto_logging fails decisively.
    assert results["auto_logging"].status is CheckStatus.not_met
    # No oversight spans → human_oversight_marker fails.
    assert results["human_oversight_marker"].status is CheckStatus.not_met
    # No token attributes → operational_monitoring fails.
    assert results["operational_monitoring"].status is CheckStatus.not_met

    # Prompts are still captured → input_recording is met.
    assert results["input_recording"].status is CheckStatus.met
    # Timestamps are valid → session_timestamps is met.
    assert results["session_timestamps"].status is CheckStatus.met
    # Retention declared via flag → met.
    assert results["log_retention"].status is CheckStatus.met
    # No errors observed → not_evidenced (honest signal — absence isn't evidence).
    assert results["incident_reporting"].status is CheckStatus.not_evidenced


def test_under_instrumented_remediation_actionable() -> None:
    """Failing checks must carry remediation text describing concrete fixes."""
    results = assess(load(FIXTURE), retention_days=365)
    for r in results:
        if r.status is CheckStatus.not_met:
            assert r.remediation, f"{r.check_id} missing remediation"
            assert len(r.remediation) > 30, (
                f"{r.check_id} remediation too brief to be actionable"
            )

"""Tests for the OTel GenAI JSONL adapter against the real toy-agent fixture."""

from __future__ import annotations

from datetime import timezone
from pathlib import Path

import pytest

from agentaudit.adapters.otel import load
from agentaudit.models import SpanKind, Trace

FIXTURE = Path(__file__).parent / "fixtures" / "otel_pass.jsonl"


@pytest.fixture(scope="module")
def traces() -> list[Trace]:
    assert FIXTURE.exists(), (
        f"Fixture missing: {FIXTURE}. Run `uv run python examples/toy_agent.py`."
    )
    return load(FIXTURE)


def test_loads_at_least_one_trace(traces: list[Trace]) -> None:
    assert len(traces) >= 1


def test_each_trace_has_spans(traces: list[Trace]) -> None:
    for t in traces:
        assert t.spans, f"trace {t.trace_id} has no spans"


def test_each_trace_has_agent_llm_and_oversight_spans(traces: list[Trace]) -> None:
    for t in traces:
        kinds = {s.kind for s in t.spans}
        assert SpanKind.agent in kinds, f"trace {t.trace_id} missing agent span"
        assert SpanKind.llm in kinds, f"trace {t.trace_id} missing llm span"
        assert SpanKind.oversight in kinds, (
            f"trace {t.trace_id} missing oversight span"
        )


def test_llm_spans_carry_gen_ai_attributes(traces: list[Trace]) -> None:
    for t in traces:
        for s in t.spans:
            if s.kind is SpanKind.llm:
                assert s.model, f"llm span {s.span_id} missing model"
                assert s.prompt, f"llm span {s.span_id} missing prompt"
                assert s.completion, f"llm span {s.span_id} missing completion"
                assert s.input_tokens and s.input_tokens > 0
                assert s.output_tokens and s.output_tokens > 0


def test_timestamps_are_utc_and_monotonic(traces: list[Trace]) -> None:
    for t in traces:
        for s in t.spans:
            assert s.start_time.tzinfo is not None
            assert s.start_time.utcoffset() == timezone.utc.utcoffset(None)
            assert s.end_time >= s.start_time


def test_trace_ids_are_hex_32(traces: list[Trace]) -> None:
    for t in traces:
        assert len(t.trace_id) == 32
        int(t.trace_id, 16)  # raises if not hex


def test_parent_child_relationships(traces: list[Trace]) -> None:
    for t in traces:
        roots = [s for s in t.spans if not s.parent_span_id]
        assert len(roots) == 1, f"trace {t.trace_id} should have exactly 1 root"
        assert roots[0].kind is SpanKind.agent


def test_trace_start_and_end_properties(traces: list[Trace]) -> None:
    for t in traces:
        assert t.start <= t.end
        assert t.start == min(s.start_time for s in t.spans)
        assert t.end == max(s.end_time for s in t.spans)

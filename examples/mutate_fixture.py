"""Generate tests/fixtures/otel_fail.jsonl from otel_pass.jsonl by applying
deterministic mutations that decisively fail each Article 12 check.

The mutations are documented inline so a reader can map "what failed" to
"what was changed in the trace data" — this fixture also doubles as the
example the README uses to show the report's failure presentation.

Run:
    uv run python examples/mutate_fixture.py
"""

from __future__ import annotations

import copy
import json
import pathlib
from typing import Any

PASS_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "tests"
    / "fixtures"
    / "otel_pass.jsonl"
)
FAIL_PATH = PASS_PATH.parent / "otel_fail.jsonl"


def _attr_value(span: dict[str, Any], key: str) -> Any:
    for a in span.get("attributes", []):
        if a["key"] == key:
            v = a["value"]
            return next(iter(v.values()))
    return None


def _kind(span: dict[str, Any]) -> str | None:
    return _attr_value(span, "agentaudit.kind")


def _strip_attr(span: dict[str, Any], key: str) -> None:
    span["attributes"] = [a for a in span.get("attributes", []) if a["key"] != key]


def _drop_span(batches: list[dict[str, Any]], span_id: str) -> None:
    for batch in batches:
        for rs in batch["resourceSpans"]:
            for ss in rs["scopeSpans"]:
                ss["spans"] = [s for s in ss["spans"] if s["spanId"] != span_id]


def _all_spans(batches: list[dict[str, Any]]):
    for batch in batches:
        for rs in batch["resourceSpans"]:
            for ss in rs["scopeSpans"]:
                yield from ss["spans"]


def _spans_for_trace(batches: list[dict[str, Any]], trace_id: str) -> list[dict[str, Any]]:
    return [s for s in _all_spans(batches) if s["traceId"] == trace_id]


def _ordered_trace_ids(batches: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for s in _all_spans(batches):
        if s["traceId"] not in seen:
            seen.append(s["traceId"])
    return seen


def _find_kind(batches: list[dict[str, Any]], trace_id: str, kind: str) -> dict[str, Any] | None:
    for s in _spans_for_trace(batches, trace_id):
        if _kind(s) == kind:
            return s
    return None


def _drop_empty_scopes(batches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for batch in batches:
        rs_keep = []
        for rs in batch["resourceSpans"]:
            ss_keep = [ss for ss in rs["scopeSpans"] if ss["spans"]]
            if ss_keep:
                rs["scopeSpans"] = ss_keep
                rs_keep.append(rs)
        if rs_keep:
            batch["resourceSpans"] = rs_keep
            cleaned.append(batch)
    return cleaned


def main() -> None:
    raw = [
        json.loads(line)
        for line in PASS_PATH.read_text().splitlines()
        if line.strip()
    ]
    batches = copy.deepcopy(raw)
    trace_ids = _ordered_trace_ids(batches)
    if len(trace_ids) < 5:
        raise SystemExit(
            f"Expected ≥5 traces in {PASS_PATH}, found {len(trace_ids)}. "
            "Re-run examples/toy_agent.py first."
        )
    t1, t2, t3, t4, t5 = trace_ids[:5]

    # Trace 1: drop agent root + drop oversight
    #   → contributes to auto_logging fail and human_oversight fail
    _drop_span(batches, _find_kind(batches, t1, "agent")["spanId"])
    _drop_span(batches, _find_kind(batches, t1, "oversight")["spanId"])

    # Trace 2: drop agent root + drop oversight + drop tokens on llm
    #   → contributes to auto_logging, human_oversight, operational_monitoring
    _drop_span(batches, _find_kind(batches, t2, "agent")["spanId"])
    _drop_span(batches, _find_kind(batches, t2, "oversight")["spanId"])
    llm2 = _find_kind(batches, t2, "llm")
    _strip_attr(llm2, "gen_ai.usage.input_tokens")
    _strip_attr(llm2, "gen_ai.usage.output_tokens")

    # Trace 3: strip prompt + strip tokens on llm
    #   → contributes to input_recording and operational_monitoring fails
    llm3 = _find_kind(batches, t3, "llm")
    _strip_attr(llm3, "gen_ai.prompt")
    _strip_attr(llm3, "gen_ai.usage.input_tokens")
    _strip_attr(llm3, "gen_ai.usage.output_tokens")

    # Trace 4: strip prompt on llm + drop oversight
    #   → contributes to input_recording and human_oversight fails
    llm4 = _find_kind(batches, t4, "llm")
    _strip_attr(llm4, "gen_ai.prompt")
    _drop_span(batches, _find_kind(batches, t4, "oversight")["spanId"])

    # Trace 5: drop oversight + swap llm timestamps + add unstructured error event
    #   → contributes to human_oversight, fails session_timestamps,
    #     fails incident_reporting (error has only message, no exception.type)
    _drop_span(batches, _find_kind(batches, t5, "oversight")["spanId"])
    llm5 = _find_kind(batches, t5, "llm")
    llm5["startTimeUnixNano"], llm5["endTimeUnixNano"] = (
        llm5["endTimeUnixNano"],
        llm5["startTimeUnixNano"],
    )
    llm5["events"] = [
        {
            "name": "exception",
            "timeUnixNano": llm5["startTimeUnixNano"],
            "attributes": [
                {
                    "key": "exception.message",
                    "value": {"stringValue": "TOOL_TIMEOUT after 30s"},
                }
            ],
        }
    ]
    llm5["status"] = {"code": 2, "message": "TOOL_TIMEOUT after 30s"}

    cleaned = _drop_empty_scopes(batches)
    FAIL_PATH.write_text("\n".join(json.dumps(b) for b in cleaned) + "\n")
    print(f"Wrote {len(cleaned)} batches to {FAIL_PATH}")


if __name__ == "__main__":
    main()

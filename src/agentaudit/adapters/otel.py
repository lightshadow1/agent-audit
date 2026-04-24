"""OpenTelemetry GenAI JSONL adapter.

Reads OTLP-JSON lines (one exported batch per line, `{"resourceSpans": [...]}`)
and produces AgentAudit `Trace` and `Span` objects.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentaudit.models import Span, SpanKind, Trace


def load(path: str | Path) -> list[Trace]:
    """Load a list of Traces from an OTLP-JSON newline-delimited file."""
    spans: list[Span] = []
    with open(path) as f:
        for line_no, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                batch = json.loads(raw)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON on line {line_no}: {e}") from e
            spans.extend(_spans_from_batch(batch))

    by_trace: dict[str, list[Span]] = defaultdict(list)
    for s in spans:
        by_trace[s.trace_id].append(s)

    return [
        Trace(trace_id=tid, spans=sorted(ss, key=lambda s: s.start_time))
        for tid, ss in by_trace.items()
    ]


def _spans_from_batch(batch: dict[str, Any]) -> list[Span]:
    out: list[Span] = []
    for rs in batch.get("resourceSpans", []):
        for ss in rs.get("scopeSpans", []):
            for sp in ss.get("spans", []):
                out.append(_map_span(sp))
    return out


def _map_span(sp: dict[str, Any]) -> Span:
    attrs = _attrs_to_dict(sp.get("attributes", []))
    events = sp.get("events", [])

    kind_attr = str(attrs.get("agentaudit.kind", "")).lower()
    if kind_attr in {"llm", "tool", "agent", "oversight"}:
        kind = SpanKind(kind_attr)
    elif "gen_ai.system" in attrs or "gen_ai.request.model" in attrs:
        kind = SpanKind.llm
    elif attrs.get("gen_ai.tool.name"):
        kind = SpanKind.tool
    else:
        kind = SpanKind.agent

    error_type, error_message = _extract_error(sp.get("status", {}), events)

    clean_attrs: dict[str, str | int | float | bool] = {
        k: v for k, v in attrs.items() if isinstance(v, str | int | float | bool)
    }

    return Span(
        trace_id=sp["traceId"],
        span_id=sp["spanId"],
        parent_span_id=sp.get("parentSpanId") or None,
        kind=kind,
        name=sp.get("name", ""),
        start_time=_nano_to_dt(sp["startTimeUnixNano"]),
        end_time=_nano_to_dt(sp["endTimeUnixNano"]),
        model=_as_str(attrs.get("gen_ai.request.model")),
        input_tokens=_as_int(attrs.get("gen_ai.usage.input_tokens")),
        output_tokens=_as_int(attrs.get("gen_ai.usage.output_tokens")),
        prompt=_as_str(attrs.get("gen_ai.prompt")),
        completion=_as_str(attrs.get("gen_ai.completion")),
        error_type=error_type,
        error_message=error_message,
        attributes=clean_attrs,
    )


def _attrs_to_dict(attrs: list[dict[str, Any]]) -> dict[str, Any]:
    """Flatten OTLP attribute list (AnyValue wrappers) to a plain dict."""
    out: dict[str, Any] = {}
    for a in attrs:
        key = a.get("key")
        val = a.get("value", {})
        if key is None:
            continue
        if "stringValue" in val:
            out[key] = val["stringValue"]
        elif "intValue" in val:
            out[key] = int(val["intValue"])
        elif "doubleValue" in val:
            out[key] = float(val["doubleValue"])
        elif "boolValue" in val:
            out[key] = bool(val["boolValue"])
        elif "arrayValue" in val:
            out[key] = json.dumps(val["arrayValue"])
    return out


def _extract_error(
    status: dict[str, Any], events: list[dict[str, Any]]
) -> tuple[str | None, str | None]:
    if status.get("code") != 2:  # STATUS_CODE_ERROR
        status_msg = None
    else:
        status_msg = status.get("message") or None

    for ev in events:
        if ev.get("name") == "exception":
            ev_attrs = _attrs_to_dict(ev.get("attributes", []))
            return _as_str(ev_attrs.get("exception.type")), _as_str(
                ev_attrs.get("exception.message")
            ) or status_msg
    return (None, status_msg)


def _nano_to_dt(ns: str | int) -> datetime:
    return datetime.fromtimestamp(int(ns) / 1_000_000_000, tz=timezone.utc)


def _as_str(v: Any) -> str | None:
    return None if v is None else str(v)


def _as_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None

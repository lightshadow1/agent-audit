"""A deliberately under-instrumented agent — emits ONLY LLM spans.

Where `toy_agent.py` shows what well-instrumented traces look like, this
script shows what realistic gaps look like. It runs real Anthropic calls
but skips:

- the agent-kind root span (so auto_logging fails)
- the oversight-kind span (so human_oversight_marker fails)
- the gen_ai.usage.* token attributes (so operational_monitoring fails)

The resulting fixture (`tests/fixtures/otel_under_instrumented.jsonl`)
demonstrates how the same Article 12 assessment surfaces gaps from real
instrumentation choices, not from synthetic mutations.

Run:
    export ANTHROPIC_API_KEY=sk-ant-...
    uv run python examples/under_instrumented_agent.py
"""

from __future__ import annotations

import json
import os
import pathlib
from typing import Any

import anthropic
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)

FIXTURE_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "tests"
    / "fixtures"
    / "otel_under_instrumented.jsonl"
)

MODEL = "claude-haiku-4-5"

PROMPTS = [
    "In one sentence, what is OTLP?",
    "In one sentence, what is a span attribute?",
    "In one sentence, what is a tracer?",
    "In one sentence, what is a span context?",
    "In one sentence, what is a trace ID?",
]


class JsonlOtlpExporter(SpanExporter):
    """Appends one OTLP-JSON `{"resourceSpans": [...]}` batch per span export."""

    def __init__(self, path: pathlib.Path, service_name: str) -> None:
        self.path = path
        self.service_name = service_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")

    def export(self, spans: list[ReadableSpan]) -> SpanExportResult:
        batch = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [_attr("service.name", self.service_name)]
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": self.service_name, "version": "0.1.0"},
                            "spans": [_span_to_otlp(s) for s in spans],
                        }
                    ],
                }
            ]
        }
        with self.path.open("a") as f:
            f.write(json.dumps(batch) + "\n")
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


def _attr(key: str, value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    return {"key": key, "value": {"stringValue": str(value)}}


def _span_to_otlp(span: ReadableSpan) -> dict[str, Any]:
    ctx = span.get_span_context()
    parent = span.parent
    return {
        "traceId": format(ctx.trace_id, "032x"),
        "spanId": format(ctx.span_id, "016x"),
        "parentSpanId": format(parent.span_id, "016x") if parent else "",
        "name": span.name,
        "startTimeUnixNano": str(span.start_time),
        "endTimeUnixNano": str(span.end_time),
        "attributes": [_attr(k, v) for k, v in (span.attributes or {}).items()],
        "status": {"code": span.status.status_code.value},
    }


def _setup_tracer() -> trace.Tracer:
    provider = TracerProvider(
        resource=Resource.create({"service.name": "under_instrumented_agent"})
    )
    provider.add_span_processor(
        SimpleSpanProcessor(JsonlOtlpExporter(FIXTURE_PATH, "under_instrumented_agent"))
    )
    trace.set_tracer_provider(provider)
    return trace.get_tracer("under_instrumented_agent")


def run_one(tracer: trace.Tracer, client: anthropic.Anthropic, prompt: str) -> None:
    # NOTE: no agent-kind root span, no oversight span — only the LLM call.
    # NOTE: no gen_ai.usage.* attributes recorded.
    with tracer.start_as_current_span(
        "anthropic_messages_create",
        attributes={
            "agentaudit.kind": "llm",
            "gen_ai.system": "anthropic",
            "gen_ai.request.model": MODEL,
            "gen_ai.prompt": prompt,
        },
    ) as llm_span:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=128,
            messages=[{"role": "user", "content": prompt}],
        )
        completion = resp.content[0].text if resp.content else ""
        llm_span.set_attribute("gen_ai.completion", completion)


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "ANTHROPIC_API_KEY not set. Export it before running this agent."
        )

    tracer = _setup_tracer()
    client = anthropic.Anthropic()

    for prompt in PROMPTS:
        run_one(tracer, client, prompt)

    trace.get_tracer_provider().shutdown()
    print(f"Wrote {len(PROMPTS)} under-instrumented traces to {FIXTURE_PATH}")


if __name__ == "__main__":
    main()

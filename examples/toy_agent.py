"""Toy agent that emits real OpenTelemetry GenAI spans to a JSONL fixture.

Makes N real Anthropic API calls with `claude-haiku-4-5`, instruments each
call with OpenTelemetry, and writes one OTLP-JSON batch per line to
`tests/fixtures/otel_pass.jsonl`.

Each trace contains:
- one `agent`-kind root span (the research task)
- one `llm`-kind span (the Anthropic call, with gen_ai.* attributes)
- one `oversight`-kind span (simulated human-in-the-loop approval)

Run:
    export ANTHROPIC_API_KEY=sk-ant-...
    uv run python examples/toy_agent.py
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
    / "otel_pass.jsonl"
)

MODEL = "claude-haiku-4-5"

PROMPTS = [
    "In one sentence, what is the EU AI Act?",
    "In one sentence, what is OpenTelemetry?",
    "In one sentence, what is SOC 2?",
    "In one sentence, what is NIST AI RMF?",
    "In one sentence, what is ISO/IEC 42001?",
]


class JsonlOtlpExporter(SpanExporter):
    """Appends one OTLP-JSON `{"resourceSpans": [...]}` batch per span export."""

    def __init__(self, path: pathlib.Path, service_name: str = "toy_agent") -> None:
        self.path = path
        self.service_name = service_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")

    def export(self, spans: list[ReadableSpan]) -> SpanExportResult:
        resource_attrs = [_attr("service.name", self.service_name)]
        scope = {"name": "toy_agent", "version": "0.1.0"}
        mapped = [_span_to_otlp(s) for s in spans]
        batch = {
            "resourceSpans": [
                {
                    "resource": {"attributes": resource_attrs},
                    "scopeSpans": [{"scope": scope, "spans": mapped}],
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
    provider = TracerProvider(resource=Resource.create({"service.name": "toy_agent"}))
    provider.add_span_processor(SimpleSpanProcessor(JsonlOtlpExporter(FIXTURE_PATH)))
    trace.set_tracer_provider(provider)
    return trace.get_tracer("toy_agent")


def run_one(tracer: trace.Tracer, client: anthropic.Anthropic, prompt: str) -> None:
    with tracer.start_as_current_span(
        "research_task", attributes={"agentaudit.kind": "agent"}
    ):
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
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            completion = resp.content[0].text if resp.content else ""
            llm_span.set_attribute("gen_ai.completion", completion)
            llm_span.set_attribute(
                "gen_ai.usage.input_tokens", resp.usage.input_tokens
            )
            llm_span.set_attribute(
                "gen_ai.usage.output_tokens", resp.usage.output_tokens
            )
            llm_span.set_attribute("gen_ai.response.model", resp.model)

        with tracer.start_as_current_span(
            "human_approval",
            attributes={
                "agentaudit.kind": "oversight",
                "agentaudit.oversight.reviewer": "toy_reviewer",
                "agentaudit.oversight.decision": "approved",
            },
        ):
            pass


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "ANTHROPIC_API_KEY not set. Export it before running the toy agent."
        )

    tracer = _setup_tracer()
    client = anthropic.Anthropic()

    for prompt in PROMPTS:
        run_one(tracer, client, prompt)

    trace.get_tracer_provider().shutdown()
    print(f"Wrote {len(PROMPTS)} traces to {FIXTURE_PATH}")


if __name__ == "__main__":
    main()

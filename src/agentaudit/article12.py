"""EU AI Act Article 12 assessment.

Each check is intentionally narrow: it returns a CheckResult based only on
what OpenTelemetry traces can evidence. Sub-requirements that need artifacts
outside trace data are listed under `not_trace_evidenceable` in the YAML and
surfaced by the report layer rather than scored here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agentaudit.models import (
    CheckResult,
    CheckStatus,
    Evidenceability,
    SpanKind,
    Trace,
)

RULES_PATH = Path(__file__).parent / "rules" / "article12.yaml"
RULES: dict[str, Any] = yaml.safe_load(RULES_PATH.read_text())
_BY_ID: dict[str, dict[str, Any]] = {c["id"]: c for c in RULES["checks"]}


def assess(traces: list[Trace], retention_days: int | None = None) -> list[CheckResult]:
    """Run all 7 trace-evidenceable Article 12 checks."""
    return [
        _auto_logging(traces),
        _session_timestamps(traces),
        _input_recording(traces),
        _operational_monitoring(traces),
        _human_oversight_marker(traces),
        _log_retention(retention_days),
        _incident_reporting(traces),
    ]


def _status_from_pct(rate: float, threshold_pct: int) -> CheckStatus:
    threshold = threshold_pct / 100.0
    if rate >= threshold:
        return CheckStatus.met
    if rate >= 0.8 * threshold:
        return CheckStatus.partial
    return CheckStatus.not_met


def _build(
    rule: dict[str, Any],
    status: CheckStatus,
    evidence: list[str],
    gap: str | None = None,
) -> CheckResult:
    return CheckResult(
        check_id=rule["id"],
        article=rule["article"],
        name=rule["name"],
        evidenceability=Evidenceability(rule["evidenceability"]),
        status=status,
        evidence=evidence[:5],
        gap=gap,
        remediation=rule["remediation"].strip()
        if status is not CheckStatus.met
        else None,
    )


def _no_data(rule: dict[str, Any], reason: str) -> CheckResult:
    return _build(
        rule,
        CheckStatus.not_evidenced,
        [reason],
        gap=f"Cannot evaluate from trace data: {reason}",
    )


def _auto_logging(traces: list[Trace]) -> CheckResult:
    rule = _BY_ID["auto_logging"]
    if not traces:
        return _no_data(rule, "no traces supplied")

    covered = [t for t in traces if any(s.kind is SpanKind.agent for s in t.spans)]
    rate = len(covered) / len(traces)
    status = _status_from_pct(rate, rule["threshold_pct"])

    evidence = [
        f"{len(covered)}/{len(traces)} traces have an agent-kind root span ({rate:.0%})"
    ]
    missing = [t.trace_id[:16] for t in traces if t not in covered][:3]
    if missing:
        evidence.append("Missing agent span in: " + ", ".join(missing))

    gap = (
        None
        if status is CheckStatus.met
        else f"{rate:.0%} agent-span coverage; threshold is {rule['threshold_pct']}%"
    )
    return _build(rule, status, evidence, gap)


def _session_timestamps(traces: list[Trace]) -> CheckResult:
    rule = _BY_ID["session_timestamps"]
    if not traces:
        return _no_data(rule, "no traces supplied")

    total_spans = sum(len(t.spans) for t in traces)
    bad: list[str] = []
    for t in traces:
        for s in t.spans:
            if s.end_time < s.start_time:
                bad.append(f"{t.trace_id[:8]}/{s.span_id[:8]} end<start")
    rate = (total_spans - len(bad)) / total_spans if total_spans else 0.0
    status = _status_from_pct(rate, rule["threshold_pct"])

    evidence = [
        f"{total_spans - len(bad)}/{total_spans} spans have end_time >= start_time ({rate:.0%})"
    ]
    if bad:
        evidence.append("Violations: " + "; ".join(bad[:3]))

    gap = None if status is CheckStatus.met else f"{len(bad)} span(s) have end_time < start_time"
    return _build(rule, status, evidence, gap)


def _input_recording(traces: list[Trace]) -> CheckResult:
    rule = _BY_ID["input_recording"]
    llm_spans = [s for t in traces for s in t.spans if s.kind is SpanKind.llm]
    if not llm_spans:
        return _no_data(rule, "no LLM spans found")

    with_prompt = [s for s in llm_spans if s.prompt]
    rate = len(with_prompt) / len(llm_spans)
    status = _status_from_pct(rate, rule["threshold_pct"])

    evidence = [
        f"{len(with_prompt)}/{len(llm_spans)} LLM spans carry a prompt ({rate:.0%})"
    ]
    if with_prompt:
        sample = with_prompt[0].prompt or ""
        evidence.append(f"Sample prompt: {sample[:120]}")

    gap = (
        None
        if status is CheckStatus.met
        else f"{rate:.0%} prompt coverage; threshold is {rule['threshold_pct']}%"
    )
    return _build(rule, status, evidence, gap)


def _operational_monitoring(traces: list[Trace]) -> CheckResult:
    rule = _BY_ID["operational_monitoring"]
    llm_spans = [s for t in traces for s in t.spans if s.kind is SpanKind.llm]
    if not llm_spans:
        return _no_data(rule, "no LLM spans found")

    with_tokens = [
        s for s in llm_spans if s.input_tokens is not None and s.output_tokens is not None
    ]
    rate = len(with_tokens) / len(llm_spans)
    status = _status_from_pct(rate, rule["threshold_pct"])

    evidence = [
        f"{len(with_tokens)}/{len(llm_spans)} LLM spans report token usage ({rate:.0%})"
    ]
    if with_tokens:
        s = with_tokens[0]
        evidence.append(
            f"Sample: model={s.model}, input={s.input_tokens}, output={s.output_tokens}"
        )

    gap = (
        None
        if status is CheckStatus.met
        else f"{rate:.0%} token-usage coverage; threshold is {rule['threshold_pct']}%"
    )
    return _build(rule, status, evidence, gap)


def _human_oversight_marker(traces: list[Trace]) -> CheckResult:
    rule = _BY_ID["human_oversight_marker"]
    if not traces:
        return _no_data(rule, "no traces supplied")

    marked = [t for t in traces if any(s.kind is SpanKind.oversight for s in t.spans)]
    rate = len(marked) / len(traces)
    status = _status_from_pct(rate, rule["threshold_pct"])

    evidence = [
        f"{len(marked)}/{len(traces)} traces include an oversight-kind span ({rate:.0%})"
    ]
    evidence.append(
        "Note: a marker proves a step was tagged for oversight, not that "
        "meaningful human review occurred — see Evidenceability=partially."
    )

    gap = (
        None
        if status is CheckStatus.met
        else f"{rate:.0%} oversight-marker coverage; threshold is {rule['threshold_pct']}%"
    )
    return _build(rule, status, evidence, gap)


def _log_retention(retention_days: int | None) -> CheckResult:
    rule = _BY_ID["log_retention"]
    if retention_days is None:
        return _no_data(
            rule,
            "no retention policy declared (pass --retention-days to evaluate)",
        )

    threshold = rule["threshold_days"]
    if retention_days >= threshold:
        status = CheckStatus.met
    elif retention_days >= int(0.5 * threshold):
        status = CheckStatus.partial
    else:
        status = CheckStatus.not_met

    evidence = [
        f"Declared retention: {retention_days} days; Article 26(6) minimum: {threshold} days"
    ]
    gap = (
        None
        if status is CheckStatus.met
        else f"Declared {retention_days} days falls below {threshold}-day minimum"
    )
    return _build(rule, status, evidence, gap)


def _incident_reporting(traces: list[Trace]) -> CheckResult:
    rule = _BY_ID["incident_reporting"]
    error_spans = [
        s
        for t in traces
        for s in t.spans
        if s.error_type is not None or s.error_message is not None
    ]
    if not error_spans:
        return _no_data(
            rule,
            "no error spans observed; cannot evaluate incident-reporting structure",
        )

    structured = [s for s in error_spans if s.error_type]
    rate = len(structured) / len(error_spans)
    status = _status_from_pct(rate, rule["threshold_pct"])

    evidence = [
        f"{len(structured)}/{len(error_spans)} error spans have a structured exception.type ({rate:.0%})"
    ]
    if not structured and error_spans:
        sample = error_spans[0]
        evidence.append(
            f"Unstructured example: trace={sample.trace_id[:8]}, message={sample.error_message!r}"
        )

    gap = (
        None
        if status is CheckStatus.met
        else "Errors are recorded with free-text messages but no structured exception.type"
    )
    return _build(rule, status, evidence, gap)

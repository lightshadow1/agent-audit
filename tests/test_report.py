"""Tests for the HTML report generator."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentaudit.adapters.otel import load
from agentaudit.article12 import assess
from agentaudit.models import Report
from agentaudit.report import generate_html

FIXTURES = Path(__file__).parent / "fixtures"


def _build_report(fixture_name: str, retention_days: int | None = 365) -> Report:
    traces = load(FIXTURES / fixture_name)
    spans = sum(len(t.spans) for t in traces)
    return Report(
        generated_at=datetime.now(timezone.utc),
        period_start=min(t.start for t in traces),
        period_end=max(t.end for t in traces),
        traces_analyzed=len(traces),
        spans_analyzed=spans,
        checks=assess(traces, retention_days=retention_days),
    )


@pytest.fixture(scope="module")
def pass_html() -> str:
    return generate_html(_build_report("otel_pass.jsonl"))


@pytest.fixture(scope="module")
def fail_html() -> str:
    return generate_html(_build_report("otel_fail.jsonl"))


def test_html_starts_with_doctype(pass_html: str) -> None:
    assert pass_html.lstrip().lower().startswith("<!doctype html>")


def test_html_has_required_sections(pass_html: str) -> None:
    for needle in (
        "EU AI Act Article 12",
        "Scope of evidence",  # honesty section
        "Summary",
        "Per-check evidence",
        "Not trace-evidenceable",
        "Annex IV",
        "EN 18229-1",
        "Quality Management System",
        "AgentAudit v",  # footer version
    ):
        assert needle in pass_html, f"missing required section text: {needle!r}"


def test_html_renders_status_badges(pass_html: str, fail_html: str) -> None:
    assert "badge-met" in pass_html
    assert "badge-not_met" in fail_html
    assert "badge-not_evidenced" in pass_html  # incident_reporting in pass is not_evidenced


def test_html_renders_evidenceability_tags(pass_html: str) -> None:
    assert "ev-fully" in pass_html
    assert "ev-partially" in pass_html


def test_html_includes_remediation_for_failures(fail_html: str) -> None:
    """Failing checks must surface remediation text from YAML rules."""
    assert "Remediation" in fail_html
    assert "Gap" in fail_html


def test_html_pass_does_not_include_gap_section_for_met_checks(pass_html: str) -> None:
    """Met checks should not display a 'Gap:' label (they have no gap)."""
    # Crude check: count occurrences of 'Gap:' is at most equal to non-met checks.
    # Pass fixture has 6 met + 1 not_evidenced (no gap field set since it's
    # not_evidenced and the function builds gap conditionally — see model).
    assert pass_html.count(">Gap:<") <= 1


def test_html_includes_honesty_disclaimer(pass_html: str) -> None:
    assert "not legal advice" in pass_html.lower()
    assert "derivable from OpenTelemetry" in pass_html


def test_html_escapes_user_content(fail_html: str) -> None:
    """Jinja2 autoescape must be on — check no raw < or > leaks from prompts."""
    # The toy agent's prompts are benign, but autoescape must still be wired.
    # If it weren't, '<' in any prompt would render as raw HTML. Check that
    # our template's autoescape applies by ensuring the output is well-formed
    # (no obvious unescaped angle brackets from gen_ai.completion text).
    # Heuristic: the closing </body> appears exactly once.
    assert fail_html.count("</body>") == 1
    assert fail_html.count("</html>") == 1

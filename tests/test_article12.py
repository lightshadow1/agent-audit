"""Tests for the Article 12 assessment module."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentaudit.adapters.otel import load
from agentaudit.article12 import assess
from agentaudit.models import CheckStatus, Evidenceability

FIXTURES = Path(__file__).parent / "fixtures"
PASS_FIXTURE = FIXTURES / "otel_pass.jsonl"
FAIL_FIXTURE = FIXTURES / "otel_fail.jsonl"


@pytest.fixture(scope="module")
def pass_results() -> dict:
    return {r.check_id: r for r in assess(load(PASS_FIXTURE), retention_days=365)}


@pytest.fixture(scope="module")
def fail_results() -> dict:
    return {r.check_id: r for r in assess(load(FAIL_FIXTURE), retention_days=365)}


# --- Pass fixture: well-instrumented traces should clear every trace-derived check.

@pytest.mark.parametrize(
    "check_id",
    [
        "auto_logging",
        "session_timestamps",
        "input_recording",
        "operational_monitoring",
        "human_oversight_marker",
        "log_retention",
    ],
)
def test_pass_fixture_meets(check_id: str, pass_results: dict) -> None:
    result = pass_results[check_id]
    assert result.status is CheckStatus.met, (
        f"{check_id} should be met on pass fixture, got {result.status}"
    )
    assert result.remediation is None
    assert result.evidence


def test_pass_incident_reporting_is_not_evidenced(pass_results: dict) -> None:
    """No errors in the pass fixture → cannot judge incident-reporting structure.
    'not_evidenced' is the honest signal here, NOT 'met' — there is no positive
    evidence of structured incident handling, only an absence of incidents."""
    r = pass_results["incident_reporting"]
    assert r.status is CheckStatus.not_evidenced


# --- Fail fixture: each mutation produces a specific status downgrade.

@pytest.mark.parametrize(
    "check_id, expected_status",
    [
        # 3/5 traces with agent root (60%) < 76% partial floor → not_met
        ("auto_logging", CheckStatus.not_met),
        # 8/9 spans monotonic (89%) — within [80%, 100%) → partial
        ("session_timestamps", CheckStatus.partial),
        # 3/5 LLM spans with prompt (60%) < 64% partial floor → not_met
        ("input_recording", CheckStatus.not_met),
        # 3/5 LLM spans with tokens (60%) < 76% partial floor → not_met
        ("operational_monitoring", CheckStatus.not_met),
        # 1/5 traces have oversight (20%) < 40% partial floor → not_met
        ("human_oversight_marker", CheckStatus.not_met),
        # 0/1 errors carry structured exception.type → not_met
        ("incident_reporting", CheckStatus.not_met),
    ],
)
def test_fail_fixture_status(
    check_id: str, expected_status: CheckStatus, fail_results: dict
) -> None:
    actual = fail_results[check_id].status
    assert actual is expected_status, (
        f"{check_id}: expected {expected_status.value}, got {actual.value}"
    )


def test_fail_fixture_results_carry_remediation(fail_results: dict) -> None:
    for check_id, r in fail_results.items():
        if r.status in (CheckStatus.not_met, CheckStatus.partial):
            assert r.remediation, f"{check_id}: missing remediation when status={r.status.value}"
            assert r.gap, f"{check_id}: missing gap description when status={r.status.value}"


# --- Log retention: parametrized policy values, no traces required.

@pytest.mark.parametrize(
    "days, expected",
    [
        (None, CheckStatus.not_evidenced),
        (30, CheckStatus.not_met),
        (89, CheckStatus.not_met),  # below 50% of 180
        (90, CheckStatus.partial),  # >= 50% of 180
        (179, CheckStatus.partial),
        (180, CheckStatus.met),
        (365, CheckStatus.met),
    ],
)
def test_log_retention_thresholds(days: int | None, expected: CheckStatus) -> None:
    results = {r.check_id: r for r in assess([], retention_days=days)}
    assert results["log_retention"].status is expected


# --- Empty input: every check that needs traces should return not_evidenced.

def test_empty_traces_yield_not_evidenced() -> None:
    results = {r.check_id: r for r in assess([], retention_days=None)}
    expected_not_evidenced = [
        "auto_logging",
        "session_timestamps",
        "input_recording",
        "operational_monitoring",
        "human_oversight_marker",
        "log_retention",
        "incident_reporting",
    ]
    for cid in expected_not_evidenced:
        assert results[cid].status is CheckStatus.not_evidenced, (
            f"{cid} should be not_evidenced on empty input"
        )


# --- Evidenceability tags must match the YAML rule definitions.

def test_evidenceability_tags(pass_results: dict) -> None:
    expected = {
        "auto_logging": Evidenceability.fully,
        "session_timestamps": Evidenceability.fully,
        "input_recording": Evidenceability.fully,
        "operational_monitoring": Evidenceability.fully,
        "human_oversight_marker": Evidenceability.partially,
        "log_retention": Evidenceability.partially,
        "incident_reporting": Evidenceability.partially,
    }
    for cid, ev in expected.items():
        assert pass_results[cid].evidenceability is ev


def test_assess_returns_seven_checks(pass_results: dict) -> None:
    assert len(pass_results) == 7

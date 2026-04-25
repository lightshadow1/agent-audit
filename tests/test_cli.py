"""End-to-end tests for the AgentAudit CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentaudit.cli import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"
PASS = FIXTURES / "otel_pass.jsonl"
FAIL = FIXTURES / "otel_fail.jsonl"
UNDER = FIXTURES / "otel_under_instrumented.jsonl"


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "agentaudit" in result.stdout


def test_report_pass_fixture_exits_zero(tmp_path: Path) -> None:
    out = tmp_path / "report.html"
    result = runner.invoke(
        app,
        [
            "report",
            str(PASS),
            "--retention-days",
            "365",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert out.read_text().lstrip().lower().startswith("<!doctype html>")


def test_report_fail_fixture_exits_one(tmp_path: Path) -> None:
    out = tmp_path / "report.html"
    result = runner.invoke(
        app,
        [
            "report",
            str(FAIL),
            "--retention-days",
            "365",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 1
    assert out.exists()


def test_report_under_instrumented_fixture_exits_one(tmp_path: Path) -> None:
    """Real under-instrumented agent traces must surface gaps and exit 1."""
    out = tmp_path / "report.html"
    result = runner.invoke(
        app,
        [
            "report",
            str(UNDER),
            "--retention-days",
            "365",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 1
    assert out.exists()


def test_report_writes_json(tmp_path: Path) -> None:
    out = tmp_path / "report.html"
    json_out = tmp_path / "report.json"
    result = runner.invoke(
        app,
        [
            "report",
            str(PASS),
            "--retention-days",
            "365",
            "--out",
            str(out),
            "--json",
            str(json_out),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(json_out.read_text())
    assert payload["traces_analyzed"] == 5
    assert len(payload["checks"]) == 7
    statuses = {c["check_id"]: c["status"] for c in payload["checks"]}
    assert statuses["auto_logging"] == "met"
    assert statuses["incident_reporting"] == "not_evidenced"


def test_report_quiet_suppresses_table(tmp_path: Path) -> None:
    out = tmp_path / "report.html"
    result = runner.invoke(
        app,
        [
            "report",
            str(PASS),
            "--retention-days",
            "365",
            "--out",
            str(out),
            "--quiet",
        ],
    )
    assert result.exit_code == 0
    assert "Article 12" not in result.stdout


def test_report_invalid_source_exits_two(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "report",
            str(PASS),
            "--source",
            "langfuse",
            "--retention-days",
            "365",
            "--out",
            str(tmp_path / "out.html"),
        ],
    )
    assert result.exit_code == 2


def test_report_missing_input_exits_two(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "report",
            str(tmp_path / "does_not_exist.jsonl"),
            "--retention-days",
            "365",
        ],
    )
    assert result.exit_code == 2


@pytest.mark.parametrize("fixture", [PASS, FAIL, UNDER])
def test_report_works_on_all_example_fixtures(
    fixture: Path, tmp_path: Path
) -> None:
    """Every shipped example fixture should run end-to-end and produce HTML."""
    out = tmp_path / f"{fixture.stem}.html"
    result = runner.invoke(
        app,
        [
            "report",
            str(fixture),
            "--retention-days",
            "365",
            "--out",
            str(out),
            "--quiet",
        ],
    )
    assert result.exit_code in (0, 1), result.output
    assert out.exists() and out.stat().st_size > 0

"""AgentAudit CLI."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from agentaudit import __version__
from agentaudit.adapters.otel import load as load_otel
from agentaudit.article12 import assess
from agentaudit.models import CheckStatus, Report
from agentaudit.report import generate_html

app = typer.Typer(
    name="agentaudit",
    help="OpenTelemetry GenAI traces → EU AI Act Article 12 evidence reports",
    add_completion=False,
)

console = Console()
err_console = Console(stderr=True)

_STATUS_STYLE = {
    CheckStatus.met: "[green]met[/green]",
    CheckStatus.partial: "[yellow]partial[/yellow]",
    CheckStatus.not_met: "[red]not met[/red]",
    CheckStatus.not_evidenced: "[dim]not evidenced[/dim]",
}


@app.command()
def report(
    input_path: Path = typer.Argument(
        ..., exists=True, readable=True, help="Path to OTel JSONL trace file."
    ),
    source: str = typer.Option(
        "otel",
        "--source",
        help="Trace source format. Only 'otel' is supported in v1.",
    ),
    retention_days: int | None = typer.Option(
        None,
        "--retention-days",
        help="Declared log retention policy in days. Article 26(6) requires ≥180.",
    ),
    out: Path | None = typer.Option(
        Path("report.html"),
        "--out",
        help="HTML report output path. Pass '' to skip HTML generation.",
    ),
    json_out: Path | None = typer.Option(
        None,
        "--json",
        help="Optional JSON report output path.",
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Suppress the terminal table."
    ),
) -> None:
    """Generate an EU AI Act Article 12 evidence report from agent traces."""
    if source != "otel":
        err_console.print(
            f"[red]Source '{source}' is not supported in v1. Use --source otel.[/red]"
        )
        raise typer.Exit(2)

    traces = load_otel(input_path)
    if not traces:
        err_console.print(f"[red]No traces loaded from {input_path}.[/red]")
        raise typer.Exit(2)

    checks = assess(traces, retention_days=retention_days)
    spans = sum(len(t.spans) for t in traces)
    rep = Report(
        generated_at=datetime.now(timezone.utc),
        period_start=min(t.start for t in traces),
        period_end=max(t.end for t in traces),
        traces_analyzed=len(traces),
        spans_analyzed=spans,
        checks=checks,
    )

    if not quiet:
        _print_terminal(rep)

    if out and str(out):
        out.write_text(generate_html(rep))
        console.print(f"[dim]HTML report written to {out}[/dim]")

    if json_out:
        json_out.write_text(rep.model_dump_json(indent=2))
        console.print(f"[dim]JSON report written to {json_out}[/dim]")

    if any(c.status is CheckStatus.not_met for c in checks):
        raise typer.Exit(1)


@app.command()
def version() -> None:
    """Print version and exit."""
    console.print(f"agentaudit {__version__}")


def _print_terminal(rep: Report) -> None:
    title = (
        f"EU AI Act Article 12 — "
        f"{rep.traces_analyzed} trace(s) / {rep.spans_analyzed} span(s)"
    )
    table = Table(title=title, title_style="bold")
    table.add_column("Check", style="cyan", no_wrap=False)
    table.add_column("Article", style="dim")
    table.add_column("Status")
    table.add_column("Evidenceability", style="dim")

    for c in rep.checks:
        table.add_row(
            c.name, c.article, _STATUS_STYLE[c.status], c.evidenceability.value
        )

    console.print()
    console.print(table)
    console.print()
    console.print(
        "[dim]Note: traces alone cannot evidence all of Article 12. "
        "Open the HTML report for the 'Not trace-evidenceable' section.[/dim]"
    )

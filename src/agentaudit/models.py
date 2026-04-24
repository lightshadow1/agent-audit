from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SpanKind(str, Enum):
    llm = "llm"
    tool = "tool"
    agent = "agent"
    oversight = "oversight"


class Span(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    kind: SpanKind
    name: str
    start_time: datetime
    end_time: datetime
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    prompt: str | None = None
    completion: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)


class Trace(BaseModel):
    trace_id: str
    spans: list[Span]

    @property
    def start(self) -> datetime:
        return min(s.start_time for s in self.spans)

    @property
    def end(self) -> datetime:
        return max(s.end_time for s in self.spans)


class Evidenceability(str, Enum):
    fully = "fully"
    partially = "partially"
    not_from_traces = "not-from-traces"


class CheckStatus(str, Enum):
    met = "met"
    partial = "partial"
    not_met = "not_met"
    not_evidenced = "not_evidenced"


class CheckResult(BaseModel):
    check_id: str
    article: str
    name: str
    evidenceability: Evidenceability
    status: CheckStatus
    evidence: list[str] = Field(default_factory=list, max_length=5)
    gap: str | None = None
    remediation: str | None = None


class Report(BaseModel):
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    traces_analyzed: int
    spans_analyzed: int
    checks: list[CheckResult]

"""Agent-level data models shared across the graph."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.models.blockchain import utcnow


class EventKind(StrEnum):
    INFO = "info"
    TOOL = "tool"
    ANALYSIS = "analysis"
    PLAN = "plan"
    REPORT = "report"
    ERROR = "error"


class AgentEvent(BaseModel):
    """A concise, public execution event.

    These are deliberately *not* chain-of-thought - they describe what
    happened at a high level so the UI can render an activity timeline.
    """

    timestamp: datetime = Field(default_factory=utcnow)
    actor: str  # "orchestrator" | "blockchain" | "analysis" | "report"
    kind: EventKind = EventKind.INFO
    message: str

    @classmethod
    def of(cls, actor: str, message: str, kind: EventKind = EventKind.INFO) -> AgentEvent:
        return cls(actor=actor, kind=kind, message=message)


class ToolRequest(BaseModel):
    """A tool invocation queued by the orchestrator, drained by the agents."""

    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    purpose: str = ""
    iteration: int = 1


class ToolResult(BaseModel):
    """Outcome of one tool execution."""

    tool: str
    ok: bool
    data: Any = None
    evidence_ids: list[str] = Field(default_factory=list)
    error: str | None = None


class InvestigationPlan(BaseModel):
    """The orchestrator's plan: how to investigate a given subject."""

    address: str = ""
    intent: str = ""
    requests: list[ToolRequest] = Field(default_factory=list)
    reasoning: str = ""
    iteration: int = 1
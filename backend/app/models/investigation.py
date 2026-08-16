"""Investigation domain models: findings, the report, and API records."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.models.agent import AgentEvent, InvestigationPlan
from app.models.blockchain import utcnow

SEVERITIES = {"informational", "low", "medium", "high"}


class Finding(BaseModel):
    """An evidence-backed observation produced by the analysis agent.

    Language is deliberately cautious: patterns are described as
    *potentially unusual* or *risk indicators*, never as proven malice.
    """

    id: str = ""  # FIND-001
    severity: str = "informational"
    category: str = ""
    title: str
    description: str
    evidence_ids: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)

    def validate_evidence(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"Invalid severity: {self.severity!r}")

    def append_evidence(self, eid: str) -> None:
        if eid not in self.evidence_ids:
            self.evidence_ids.append(eid)


class ReportSection(BaseModel):
    """One chapter of the final investigation report."""

    title: str
    narrative: str = ""
    bullets: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class FindingsSummary(BaseModel):
    total: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)
    highlights: list[str] = Field(default_factory=list)


class InvestigationReport(BaseModel):
    """Structured, evidence-referenced report produced by the report agent."""

    investigation_id: str = ""
    subject: str = ""
    chain: str = ""
    generated_at: datetime = Field(default_factory=utcnow)
    executive_summary: str = ""
    sections: list[ReportSection] = Field(default_factory=list)
    summary: FindingsSummary = Field(default_factory=FindingsSummary)
    limitations: list[str] = Field(default_factory=list)

    def section(self, title: str) -> ReportSection | None:
        for sec in self.sections:
            if sec.title == title:
                return sec
        return None


class InvestigationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class InvestigationRecord(BaseModel):
    """The live record exposed through the API and consumed by the UI."""

    id: str
    query: str
    address: str = ""
    status: InvestigationStatus = InvestigationStatus.QUEUED
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    events: list[AgentEvent] = Field(default_factory=list)
    plan: InvestigationPlan | None = None
    findings: list[Finding] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    report: InvestigationReport | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    tool_calls: int = 0
    iterations: int = 0
    error: str | None = None

    def touch(self) -> None:
        self.updated_at = utcnow()

    def public(self) -> dict[str, Any]:
        """Shape the record for API responses (JSON-safe)."""
        return self.model_dump(mode="json")
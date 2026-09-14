"""LangGraph orchestration contracts. Executed in Phase 4; defined now so later tables match."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class OrchestrationPhase(StrEnum):
    PLAN = "PLAN"
    DELEGATE = "DELEGATE"
    EXECUTE = "EXECUTE"
    REVIEW = "REVIEW"
    REVISE = "REVISE"
    COMPLETE = "COMPLETE"


ORCHESTRATION_SEQUENCE: tuple[OrchestrationPhase, ...] = (
    OrchestrationPhase.PLAN,
    OrchestrationPhase.DELEGATE,
    OrchestrationPhase.EXECUTE,
    OrchestrationPhase.REVIEW,
    OrchestrationPhase.REVISE,
    OrchestrationPhase.COMPLETE,
)


class OrchestrationState(BaseModel):
    """Structured graph state. Every execution has a task, tools, permissions, and a budget."""

    company_id: UUID
    task_id: UUID
    phase: OrchestrationPhase = OrchestrationPhase.PLAN
    context: dict[str, Any] = Field(default_factory=dict)
    available_tools: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    iteration: int = 0
    tool_calls: int = 0
    max_iterations: int = 8
    max_tool_calls: int = 40
    expected_output: str = ""
    error: str | None = None


def next_phase(phase: OrchestrationPhase) -> OrchestrationPhase | None:
    index = ORCHESTRATION_SEQUENCE.index(phase)
    if index + 1 >= len(ORCHESTRATION_SEQUENCE):
        return None
    return ORCHESTRATION_SEQUENCE[index + 1]


def budget_remaining(state: OrchestrationState) -> bool:
    return state.tool_calls < state.max_tool_calls and state.iteration < state.max_iterations

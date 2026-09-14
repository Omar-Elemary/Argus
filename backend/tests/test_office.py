"""Office projection is derived from backend facts only."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.schemas.events import ActivityEventRead, EventType
from app.schemas.office import (
    AgentRuntimeStatus,
    AgentSnapshot,
    AnimationClip,
    project_office_state,
)
from app.schemas.orchestration import (
    ORCHESTRATION_SEQUENCE,
    OrchestrationPhase,
    OrchestrationState,
    budget_remaining,
    next_phase,
)
from app.tools.specs import tools_for_permissions


def test_empty_office_when_no_agents() -> None:
    company_id = uuid4()
    state = project_office_state(company_id=company_id, agents=[], events=[])
    assert state.company_id == company_id
    assert state.occupants == []
    assert state.source_event_id is None


def test_working_agent_maps_to_typing_animation() -> None:
    agent_id = uuid4()
    company_id = uuid4()
    agents = [
        AgentSnapshot(
            id=agent_id,
            name="Maya",
            role="Market Researcher",
            status=AgentRuntimeStatus.WORKING,
            desk_index=1,
        )
    ]
    state = project_office_state(company_id=company_id, agents=agents, events=[])
    assert len(state.occupants) == 1
    assert state.occupants[0].animation == AnimationClip.TYPING
    assert state.occupants[0].current_state == AgentRuntimeStatus.WORKING


def test_help_request_event_sets_talking_and_target() -> None:
    maya = uuid4()
    adam = uuid4()
    company_id = uuid4()
    agents = [
        AgentSnapshot(id=maya, name="Maya", role="Researcher", desk_index=0),
        AgentSnapshot(id=adam, name="Adam", role="Engineer", desk_index=2),
    ]
    event = ActivityEventRead(
        id=uuid4(),
        company_id=company_id,
        agent_id=maya,
        event_type=EventType.AGENT_REQUESTED_HELP,
        payload={"from_agent_id": str(maya), "to_agent_id": str(adam)},
        timestamp=datetime.now(UTC),
    )
    state = project_office_state(company_id=company_id, agents=agents, events=[event])
    maya_state = next(item for item in state.occupants if item.agent_id == maya)
    assert maya_state.current_state == AgentRuntimeStatus.TALKING
    assert maya_state.animation == AnimationClip.SPEAKING
    assert maya_state.target_position is not None
    assert maya_state.target_position.x == 4.8


def test_orchestration_sequence_and_budget() -> None:
    assert tuple(phase.value for phase in ORCHESTRATION_SEQUENCE) == (
        "PLAN",
        "DELEGATE",
        "EXECUTE",
        "REVIEW",
        "REVISE",
        "COMPLETE",
    )
    assert next_phase(OrchestrationPhase.PLAN) == OrchestrationPhase.DELEGATE
    assert next_phase(OrchestrationPhase.COMPLETE) is None
    state = OrchestrationState(
        company_id=uuid4(),
        task_id=uuid4(),
        iteration=8,
        max_iterations=8,
        tool_calls=0,
        max_tool_calls=40,
    )
    assert budget_remaining(state) is False


def test_tools_filtered_by_permission() -> None:
    granted = tools_for_permissions({"use_web_search", "read_company_knowledge"})
    names = {item.name for item in granted}
    assert names == {"web_search", "company_memory"}

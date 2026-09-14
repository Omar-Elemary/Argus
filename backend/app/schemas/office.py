"""3D office view-model. Derived from backend events and entity rows — never the reverse."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.events import ActivityEventRead, EventType


class AnimationClip(StrEnum):
    IDLE = "idle"
    TYPING = "typing"
    READING = "reading"
    THINKING = "thinking"
    SPEAKING = "speaking"
    WALKING = "walking"
    MEETING = "meeting"
    CONCERNED = "concerned"
    COMPLETED = "completed"
    AWAY = "away"


class AgentRuntimeStatus(StrEnum):
    IDLE = "IDLE"
    WORKING = "WORKING"
    RESEARCHING = "RESEARCHING"
    THINKING = "THINKING"
    TALKING = "TALKING"
    WALKING = "WALKING"
    MEETING = "MEETING"
    REVIEWING = "REVIEWING"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    OFFLINE = "OFFLINE"


STATUS_TO_ANIMATION: dict[AgentRuntimeStatus, AnimationClip] = {
    AgentRuntimeStatus.IDLE: AnimationClip.IDLE,
    AgentRuntimeStatus.WORKING: AnimationClip.TYPING,
    AgentRuntimeStatus.RESEARCHING: AnimationClip.READING,
    AgentRuntimeStatus.THINKING: AnimationClip.THINKING,
    AgentRuntimeStatus.TALKING: AnimationClip.SPEAKING,
    AgentRuntimeStatus.WALKING: AnimationClip.WALKING,
    AgentRuntimeStatus.MEETING: AnimationClip.MEETING,
    AgentRuntimeStatus.REVIEWING: AnimationClip.READING,
    AgentRuntimeStatus.BLOCKED: AnimationClip.CONCERNED,
    AgentRuntimeStatus.COMPLETED: AnimationClip.COMPLETED,
    AgentRuntimeStatus.OFFLINE: AnimationClip.AWAY,
}


class Vec3(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class AgentSnapshot(BaseModel):
    """Minimal agent row projection used until the Agent table ships in Phase 2."""

    id: UUID
    name: str
    role: str
    status: AgentRuntimeStatus = AgentRuntimeStatus.OFFLINE
    current_task_id: UUID | None = None
    desk_index: int = 0
    current_room: str = "open-office"


class OccupantState(BaseModel):
    agent_id: UUID
    model: str = "fellow-default"
    position: Vec3
    rotation: float = 0.0
    current_room: str
    current_state: AgentRuntimeStatus
    current_task: UUID | None = None
    target_position: Vec3 | None = None
    animation: AnimationClip


class OfficeState(BaseModel):
    company_id: UUID
    generated_at: datetime
    source_event_id: UUID | None = None
    occupants: list[OccupantState] = Field(default_factory=list)


def _desk_position(desk_index: int) -> Vec3:
    return Vec3(x=float(desk_index) * 2.4, y=0.0, z=0.0)


def project_office_state(
    *,
    company_id: UUID,
    agents: list[AgentSnapshot],
    events: list[ActivityEventRead],
) -> OfficeState:
    """Pure projection: backend facts → office occupants. No Three.js."""
    latest = events[-1] if events else None
    occupants: list[OccupantState] = []
    for agent in agents:
        status = agent.status
        target: Vec3 | None = None
        if latest and latest.event_type == EventType.AGENT_REQUESTED_HELP:
            payload = latest.payload
            if str(payload.get("from_agent_id")) == str(agent.id):
                status = AgentRuntimeStatus.TALKING
                to_id = payload.get("to_agent_id")
                other = next((item for item in agents if str(item.id) == str(to_id)), None)
                if other:
                    target = _desk_position(other.desk_index)
        occupants.append(
            OccupantState(
                agent_id=agent.id,
                position=_desk_position(agent.desk_index),
                current_room=agent.current_room,
                current_state=status,
                current_task=agent.current_task_id,
                target_position=target,
                animation=STATUS_TO_ANIMATION[status],
            )
        )
    return OfficeState(
        company_id=company_id,
        generated_at=datetime.now(UTC),
        source_event_id=latest.id if latest else None,
        occupants=occupants,
    )

"""Typed activity events. The event stream is the source of truth for realtime UI."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EventType(StrEnum):
    COMPANY_CREATED = "COMPANY_CREATED"
    AGENT_CREATED = "AGENT_CREATED"
    AGENT_STARTED_TASK = "AGENT_STARTED_TASK"
    AGENT_COMPLETED_TASK = "AGENT_COMPLETED_TASK"
    AGENT_REQUESTED_HELP = "AGENT_REQUESTED_HELP"
    AGENT_SENT_MESSAGE = "AGENT_SENT_MESSAGE"
    AGENT_RECEIVED_MESSAGE = "AGENT_RECEIVED_MESSAGE"
    AGENT_DELEGATED_TASK = "AGENT_DELEGATED_TASK"
    AGENT_ENTERED_REVIEW = "AGENT_ENTERED_REVIEW"
    AGENT_BLOCKED = "AGENT_BLOCKED"
    AGENT_FAILED = "AGENT_FAILED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"


class ActivityEventRead(BaseModel):
    id: UUID
    company_id: UUID
    agent_id: UUID | None = None
    event_type: str
    task_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime

    model_config = {"from_attributes": True}

"""Company API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.schemas.events import ActivityEventRead


class CompanySettings(BaseModel):
    timezone: str = "UTC"
    locale: str = "en-US"
    work_days: list[str] = Field(default_factory=lambda: ["mon", "tue", "wed", "thu", "fri"])


class CompanyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=4000)
    mission: str = Field(default="", max_length=4000)
    industry: str = Field(default="", max_length=80)
    logo_url: HttpUrl | None = None
    settings: CompanySettings = Field(default_factory=CompanySettings)


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    mission: str | None = Field(default=None, max_length=4000)
    industry: str | None = Field(default=None, max_length=80)
    logo_url: HttpUrl | None = None
    settings: CompanySettings | None = None


class MemberRead(BaseModel):
    user_id: UUID
    full_name: str
    email: str
    role: str

    model_config = {"from_attributes": True}


class CompanyRead(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str
    mission: str
    industry: str
    logo_url: str | None
    settings: dict[str, Any]
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    role: str | None = None

    model_config = {"from_attributes": True}


class CompanyOverview(BaseModel):
    company: CompanyRead
    members: list[MemberRead]
    recent_events: list[ActivityEventRead]

"""Company service — all queries are membership-scoped."""

from __future__ import annotations

import re
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.company import Company, CompanyMembership
from app.models.event import ActivityEvent
from app.models.user import User
from app.schemas.company import (
    CompanyCreate,
    CompanyOverview,
    CompanyRead,
    CompanyUpdate,
    MemberRead,
)
from app.schemas.events import ActivityEventRead, EventType


class CompanyError(Exception):
    def __init__(self, detail: str, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", name.lower()).strip("-")
    return slug or "company"


def _company_read(company: Company, role: str | None) -> CompanyRead:
    data = CompanyRead.model_validate(company)
    return data.model_copy(update={"role": role})


async def _unique_slug(session: AsyncSession, name: str) -> str:
    base = slugify(name)
    candidate = base
    while True:
        existing = await session.execute(select(Company.id).where(Company.slug == candidate))
        if existing.scalar_one_or_none() is None:
            return candidate
        candidate = f"{base}-{uuid4().hex[:6]}"


async def _membership_for(
    session: AsyncSession, company_id: UUID, user_id: UUID
) -> CompanyMembership | None:
    result = await session.execute(
        select(CompanyMembership).where(
            CompanyMembership.company_id == company_id,
            CompanyMembership.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def create_company(
    session: AsyncSession, user: User, payload: CompanyCreate
) -> CompanyRead:
    company = Company(
        name=payload.name.strip(),
        slug=await _unique_slug(session, payload.name),
        description=payload.description.strip(),
        mission=payload.mission.strip(),
        industry=payload.industry.strip(),
        logo_url=str(payload.logo_url) if payload.logo_url else None,
        settings=payload.settings.model_dump(),
        created_by=user.id,
    )
    session.add(company)
    await session.flush()
    session.add(CompanyMembership(company_id=company.id, user_id=user.id, role="owner"))
    session.add(
        ActivityEvent(
            company_id=company.id,
            event_type=EventType.COMPANY_CREATED.value,
            payload={"name": company.name, "created_by": str(user.id)},
        )
    )
    await session.commit()
    await session.refresh(company)
    return _company_read(company, "owner")


async def list_companies(session: AsyncSession, user_id: UUID) -> list[CompanyRead]:
    result = await session.execute(
        select(CompanyMembership)
        .options(selectinload(CompanyMembership.company))
        .where(CompanyMembership.user_id == user_id)
        .order_by(CompanyMembership.created_at.desc())
    )
    memberships = result.scalars().all()
    return [_company_read(item.company, item.role) for item in memberships]


async def get_company_for_member(
    session: AsyncSession, company_id: UUID, user_id: UUID
) -> tuple[Company, CompanyMembership]:
    membership = await _membership_for(session, company_id, user_id)
    if membership is None:
        raise CompanyError("Company not found.", 404)
    result = await session.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if company is None:
        raise CompanyError("Company not found.", 404)
    return company, membership


async def update_company(
    session: AsyncSession, company_id: UUID, user_id: UUID, payload: CompanyUpdate
) -> CompanyRead:
    company, membership = await get_company_for_member(session, company_id, user_id)
    if membership.role not in {"owner", "admin"}:
        raise CompanyError("You do not have permission to update this company.", 403)
    data = payload.model_dump(exclude_unset=True)
    if "logo_url" in data:
        data["logo_url"] = str(data["logo_url"]) if data["logo_url"] else None
    if "settings" in data and data["settings"] is not None:
        data["settings"] = payload.settings.model_dump() if payload.settings else company.settings
    for key, value in data.items():
        if key in {"name", "description", "mission", "industry"} and isinstance(value, str):
            value = value.strip()
        setattr(company, key, value)
    await session.commit()
    await session.refresh(company)
    return _company_read(company, membership.role)


async def get_overview(
    session: AsyncSession, company_id: UUID, user_id: UUID
) -> CompanyOverview:
    company, membership = await get_company_for_member(session, company_id, user_id)
    members_result = await session.execute(
        select(CompanyMembership, User)
        .join(User, User.id == CompanyMembership.user_id)
        .where(CompanyMembership.company_id == company_id)
        .order_by(CompanyMembership.created_at.asc())
    )
    members = [
        MemberRead(user_id=user.id, full_name=user.full_name, email=user.email, role=row.role)
        for row, user in members_result.all()
    ]
    events_result = await session.execute(
        select(ActivityEvent)
        .where(ActivityEvent.company_id == company_id)
        .order_by(ActivityEvent.timestamp.desc())
        .limit(20)
    )
    events = [ActivityEventRead.model_validate(item) for item in events_result.scalars().all()]
    return CompanyOverview(
        company=_company_read(company, membership.role),
        members=members,
        recent_events=events,
    )

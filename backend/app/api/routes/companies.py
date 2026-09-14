"""Company routes. Membership is enforced in the service layer."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.company import CompanyCreate, CompanyOverview, CompanyRead, CompanyUpdate
from app.services.company_service import (
    CompanyError,
    create_company,
    get_company_for_member,
    get_overview,
    list_companies,
    update_company,
)

router = APIRouter(prefix="/api/v1/companies", tags=["companies"])


def _raise(exc: CompanyError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("", response_model=CompanyRead, status_code=201)
async def create(
    payload: CompanyCreate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CompanyRead:
    return await create_company(session, user, payload)


@router.get("", response_model=list[CompanyRead])
async def list_mine(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CompanyRead]:
    return await list_companies(session, user.id)


@router.get("/{company_id}", response_model=CompanyRead)
async def get_one(
    company_id: UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CompanyRead:
    try:
        company, membership = await get_company_for_member(session, company_id, user.id)
    except CompanyError as exc:
        _raise(exc)
        raise  # pragma: no cover
    return CompanyRead.model_validate(company).model_copy(update={"role": membership.role})


@router.patch("/{company_id}", response_model=CompanyRead)
async def patch(
    company_id: UUID,
    payload: CompanyUpdate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CompanyRead:
    try:
        return await update_company(session, company_id, user.id, payload)
    except CompanyError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.get("/{company_id}/overview", response_model=CompanyOverview)
async def overview(
    company_id: UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CompanyOverview:
    try:
        return await get_overview(session, company_id, user.id)
    except CompanyError as exc:
        _raise(exc)
        raise  # pragma: no cover

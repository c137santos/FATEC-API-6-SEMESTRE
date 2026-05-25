from http import HTTPStatus
from typing import Annotated

from backend.database import get_session
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.models import ConsentPolicy
from ..core.schemas import ConsentPolicyPublic

router = APIRouter(prefix='/consent-policy', tags=['consent-policy'])
T_Session = Annotated[AsyncSession, Depends(get_session)]


@router.get('/latest', response_model=ConsentPolicyPublic)
async def get_latest_consent_policy(session: T_Session):
    policy = await session.scalar(
        Select(ConsentPolicy).order_by(desc(ConsentPolicy.id)).limit(1)
    )

    if not policy:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='No consent policy found',
        )

    return policy

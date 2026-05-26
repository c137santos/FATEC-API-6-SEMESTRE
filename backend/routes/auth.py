from http import HTTPStatus
from typing import Annotated

from backend.core.audit_log import Operation
from backend.database import get_session
from backend.security import (
    create_access_token,
    get_current_user,
    verify_password,
)
from backend.services.audit_log_service import write_log
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.models import User
from ..core.schemas import Token

router = APIRouter(prefix='/auth', tags=['auth'])
T_Session = Annotated[AsyncSession, Depends(get_session)]
T_OAuth2Form = Annotated[OAuth2PasswordRequestForm, Depends()]


@router.post('/token', response_model=Token)
async def login_for_access_token(session: T_Session, form_data: T_OAuth2Form):
    user = await session.scalar(
        Select(User).where(User.email == form_data.username)
    )

    if not user or not verify_password(form_data.password, user.password):
        await write_log(
            operation=Operation.AUTH_LOGIN_FAILURE,
            user_id='0',
            entity_name='User',
        )
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='Incorrect email or password',
        )

    if not user.is_verified:
        await write_log(
            operation=Operation.AUTH_LOGIN_BLOCKED,
            user_id=user.id,
            entity_name='User',
            to_value={'reason': 'email_not_verified'},
        )
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Email não confirmado',
        )

    access_token = create_access_token(data={'sub': user.email})

    await write_log(
        operation=Operation.AUTH_LOGIN_SUCCESS,
        user_id=user.id,
        entity_name='User',
    )

    return {'access_token': access_token, 'token_type': 'Bearer'}


@router.post('/refresh_token', response_model=Token)
async def refresh_access_token(
    user: User = Depends(get_current_user),
):
    new_access_token = create_access_token(data={'sub': user.email})

    await write_log(
        operation=Operation.AUTH_LOGIN_SUCCESS,
        user_id=user.id,
        entity_name='User',
        to_value={'method': 'refresh_token'},
    )

    return {'access_token': new_access_token, 'token_type': 'bearer'}

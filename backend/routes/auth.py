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
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.models import User

router = APIRouter(prefix='/auth', tags=['auth'])
T_Session = Annotated[AsyncSession, Depends(get_session)]
T_OAuth2Form = Annotated[OAuth2PasswordRequestForm, Depends()]


@router.post('/token')
async def login_for_access_token(
    response: Response, session: T_Session, form_data: T_OAuth2Form
):
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

    response.set_cookie(
        key='access_token',
        value=access_token,
        httponly=True,
        samesite='lax',
    )

    return {'token_type': 'bearer'}


@router.post('/logout')
async def logout(response: Response):
    response.delete_cookie(key='access_token')
    return {'message': 'Logged out'}


@router.post('/refresh_token')
async def refresh_access_token(
    response: Response,
    user: User = Depends(get_current_user),
):
    new_access_token = create_access_token(data={'sub': user.email})

    await write_log(
        operation=Operation.AUTH_LOGIN_SUCCESS,
        user_id=user.id,
        entity_name='User',
        to_value={'method': 'refresh_token'},
    )

    response.set_cookie(
        key='access_token',
        value=new_access_token,
        httponly=True,
        samesite='lax',
    )

    return {'token_type': 'bearer'}

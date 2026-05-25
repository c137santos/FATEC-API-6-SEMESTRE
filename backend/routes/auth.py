from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.security import (
    create_access_token,
    get_current_user,
    verify_password,
)

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
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='Incorrect email or password',
        )

    access_token = create_access_token(data={'sub': user.email})

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

    response.set_cookie(
        key='access_token',
        value=new_access_token,
        httponly=True,
        samesite='lax',
    )

    return {'token_type': 'bearer'}

from datetime import datetime, UTC
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.security import get_current_user, get_password_hash

from ..core.models import ConsentPolicy, User
from ..core.schemas import Message, UserCreateSchema, UserList, UserPublic, UserSchema

router = APIRouter(prefix='/users', tags=['users'])
T_Session = Annotated[AsyncSession, Depends(get_session)]
T_Current_user = Annotated[User, Depends(get_current_user)]


@router.get('/me', response_model=UserPublic)
async def get_current_user_profile(current_user: T_Current_user):
    return current_user


@router.post('/', status_code=HTTPStatus.CREATED, response_model=UserPublic)
async def create_user(user: UserCreateSchema, session: T_Session):

    if not user.consented:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='Consent is required',
        )

    db_user = await session.scalar(
        Select(User).where(
            (User.username == user.username) | (User.email == user.email)
        )
    )
    if db_user:
        if db_user.username == user.username:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail='Username already exists',
            )

        elif db_user.email == user.email:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail='Email already exists',
            )

    policy = await session.scalar(
        Select(ConsentPolicy).order_by(desc(ConsentPolicy.id)).limit(1)
    )

    db_user = User(
        username=user.username,
        email=user.email,
        password=get_password_hash(user.password),
        consented_at=datetime.now(UTC).replace(tzinfo=None),
        consent_policy_id=policy.id if policy else None,
    )

    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)

    return db_user


@router.get('/', response_model=UserList)
async def read_users(session: T_Session, limit: int = 10, skip: int = 0):
    users = await session.scalars(Select(User).limit(limit).offset(skip))
    return {'users': users}


@router.put('/{user_id}', response_model=UserPublic)
async def update_user(
    user_id: int,
    user: UserSchema,
    session: T_Session,
    current_user: T_Current_user,
):

    if current_user.id != user_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail='Not enough permission'
        )

    current_user.email = user.email
    current_user.username = user.username
    current_user.password = get_password_hash(user.password)

    await session.commit()
    await session.refresh(current_user)

    return current_user


@router.delete('/{user_id}', response_model=Message)
async def delete_user(
    user_id: int, session: T_Session, current_user: T_Current_user
):

    if current_user.id != user_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail='Not enough permission'
        )

    await session.delete(current_user)
    await session.commit()

    return {'message': 'User deleted'}

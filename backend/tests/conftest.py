import factory
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from backend.app import app
from backend.database import get_session
from backend.listagem_dist import models as _listagem_dist_models  # noqa: F401
from backend.security import get_password_hash
from core.models import User, table_registry


class UserFactory(factory.Factory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'test{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@test.com')
    password = factory.LazyAttribute(lambda obj: f'{obj.username}+senha')


@pytest.fixture(scope='session')
def postgres_container():
    with PostgresContainer('postgres:16', driver='psycopg') as postgres:
        yield postgres


@pytest_asyncio.fixture(scope='session', loop_scope='session')
async def engine(postgres_container):
    url = postgres_container.get_connection_url().replace(
        'postgresql+psycopg', 'postgresql+asyncpg'
    )

    _engine = create_async_engine(url, poolclass=NullPool)

    async with _engine.begin() as conn:
        await conn.run_sync(table_registry.metadata.create_all)

    yield _engine

    async with _engine.begin() as conn:
        await conn.run_sync(table_registry.metadata.drop_all)
    await _engine.dispose()


@pytest_asyncio.fixture(loop_scope='function')
async def session(engine):
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(session):
    async def get_session_override():
        yield session

    app.dependency_overrides[get_session] = get_session_override
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def user(session):
    pwd = 'testeste'
    user_obj = UserFactory(password=get_password_hash(pwd))

    session.add(user_obj)
    await session.commit()
    await session.refresh(user_obj)

    user_obj.clean_password = pwd
    return user_obj


@pytest_asyncio.fixture()
async def other_user(session):
    pwd = 'testeste'
    user_obj = UserFactory(password=get_password_hash(pwd))
    session.add(user_obj)
    await session.commit()
    await session.refresh(user_obj)
    user_obj.clean_password = pwd
    return user_obj


@pytest_asyncio.fixture()
async def token(client, user):
    response = await client.post(
        '/auth/token',
        data={'username': user.email, 'password': user.clean_password},
    )
    return response.json()['access_token']

import uuid
import os

import factory
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from backend.app import app
from motor.motor_asyncio import AsyncIOMotorClient
from backend.database import get_session, get_mongo_async_database
from backend.core import models as _models  # noqa: F401
from backend.security import get_password_hash
from backend.core.models import User, table_registry


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
async def client(session, mongo_db):
    async def get_session_override():
        yield session

    async def get_mongo_database_override():
        yield mongo_db

    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[get_mongo_async_database] = get_mongo_database_override
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


@pytest_asyncio.fixture
async def mongo_db():
    host = os.getenv('MONGO_HOST', '127.0.0.1')
    user = os.getenv('MONGO_ROOT_USER', 'root')
    pw = os.getenv('MONGO_ROOT_PASSWORD', '1234')
    db_name = os.getenv('MONGO_DB', 'fatec_api')
    uri = f'mongodb://{user}:{pw}@{host}:27017/?authSource=admin'
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    yield client[db_name]
    client.close()


@pytest_asyncio.fixture
async def setup_test_data(mongo_db):
    colecao = mongo_db['segmentos_mt_tabular']

    test_job_id = 'test-job-' + str(uuid.uuid4())

    await colecao.insert_one({
        'job_id': test_job_id,
        'CTMT': 'ALIMENTADOR_TESTE',
        'COMP': 1500.0,
        'CONJ': '999',
        'DIST': 'DIST_TESTE',
    })

    return test_job_id


@pytest_asyncio.fixture
async def api_response(client, setup_test_data):

    response = await client.get(f'/tam/{setup_test_data}')
    return response


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    """
    Executa antes da coleta dos testes.
    Define variáveis de ambiente mínimas para evitar erros de validação do Pydantic.
    """
    os.environ.setdefault('MAIL_USERNAME', 'test_user')
    os.environ.setdefault('MAIL_PASSWORD', 'test_password')
    os.environ.setdefault('MAIL_SERVER', 'smtp.test.com')
    os.environ.setdefault('MAIL_PORT', '587')
    os.environ.setdefault('MAIL_FROM', 'admin@test.com')

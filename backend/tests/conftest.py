import uuid
import os

import factory
import pytest
import pytest_asyncio
import asyncpg
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from testcontainers.postgres import PostgresContainer

from backend.app import app
from motor.motor_asyncio import AsyncIOMotorClient
from backend.database import get_session
from backend.core import models as _models  # noqa: F401
from backend.security import get_password_hash
from backend.routes.tam import get_db
from backend.core.models import User, table_registry
from backend.routes.tam import get_pg_db 


class UserFactory(factory.Factory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'test{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@test.com')
    password = factory.LazyAttribute(lambda obj: f'{obj.username}+senha')


@pytest.fixture(scope='session')
def postgres_container():
    with PostgresContainer('postgres:16', driver='psycopg') as postgres:
        host = postgres.get_container_host_ip()
        port = postgres.get_exposed_port(5432)
        user = postgres.username
        password = postgres.password
        dbname = postgres.dbname
        
        url_sa = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"
        url_pure = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
        
        os.environ["DATABASE_URL"] = url_sa
        os.environ["POSTGRES_HOST"] = host
        os.environ["POSTGRES_PORT"] = str(port)
        
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
async def client(session, mongo_db, postgres_container):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_db] = lambda: mongo_db

    async def get_pg_db_override():
        host = postgres_container.get_container_host_ip()
        port = postgres_container.get_exposed_port(5432)
        url = f"postgresql://{postgres_container.username}:{postgres_container.password}@{host}:{port}/{postgres_container.dbname}"
        
        conn = await asyncpg.connect(url)
        try:
            yield conn
        finally:
            if not conn.is_closed():
                await conn.close()

    app.dependency_overrides[get_pg_db] = get_pg_db_override

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
    host = os.getenv("MONGO_HOST", "127.0.0.1")
    user = os.getenv("MONGO_ROOT_USER", "root")
    pw = os.getenv("MONGO_ROOT_PASSWORD", "1234")
    db_name = os.getenv("MONGO_DB", "fatec_api")
    uri = f"mongodb://{user}:{pw}@{host}:27017/?authSource=admin"
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    yield client[db_name]
    client.close()


@pytest_asyncio.fixture
async def setup_test_data(mongo_db, postgres_container):
    test_job_id = f'test-job-{uuid.uuid4()}'
    dist_id_fake = uuid.uuid4().hex
    
    url = postgres_container.get_connection_url().replace(
        'postgresql+psycopg', 'postgresql'
    )
    
    conn = await asyncpg.connect(url)
    try:
        await conn.execute(
            """
            INSERT INTO distribuidoras (id, job_id, date_gdb, dist_name)
            VALUES ($1, $2, $3, $4)
            """,
            dist_id_fake, test_job_id, 2024, "CEMIG-D"
        )
    finally:
        await conn.close()

    colecao = mongo_db['segmentos_mt_tabular']
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

    response = await client.get(f"/tam/{setup_test_data}")
    return response


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    """
    Executa antes da coleta dos testes. 
    Define variáveis de ambiente mínimas para evitar erros de validação do Pydantic.
    """
    os.environ.setdefault("MAIL_USERNAME", "test_user")
    os.environ.setdefault("MAIL_PASSWORD", "test_password")
    os.environ.setdefault("MAIL_SERVER", "smtp.test.com")
    os.environ.setdefault("MAIL_PORT", "587")
    os.environ.setdefault("MAIL_FROM", "admin@test.com")

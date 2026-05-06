import os
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import factory
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from backend.app import app
from backend.core import models as _models  # noqa: F401
from backend.core.models import User, table_registry
from backend.database import get_mongo_async_database, get_session
from backend.security import get_password_hash
from backend.services.pipeline_trigger import trigger_pipeline_flow
from backend.tasks.celery_app import celery_app


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
async def client(session, mongo_db):
    app.dependency_overrides[get_session] = lambda: session
    
    async def _get_mongo_override():
        yield mongo_db
    app.dependency_overrides[get_mongo_async_database] = _get_mongo_override

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as ac:
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


@pytest.fixture(autouse=True)
def mock_mongo_db():
    mock_db = MagicMock()
    mock_db.jobs.insert_one = AsyncMock()
    with patch("backend.services.pipeline_trigger.get_mongo_async_db") as mocked_get_db:
        mocked_get_db.return_value = mock_db
        yield mocked_get_db


@pytest_asyncio.fixture
async def setup_distribuidora(session):
    """Cria uma distribuidora com ID real da ANEEL para teste de integração fim-a-fim."""
    id_real = "75f102e3b2e54e48950d877e8a937a34" 
    nome_real = "EQUATORIAL ALAGOAS DISTRIBUIDORA DE ENERGIA S.A."
    ano_teste = 2024
    
    await session.execute(
        text("DELETE FROM distribuidoras WHERE id = :id AND date_gdb = :ano"),
        {"id": id_real, "ano": ano_teste}
    )
    
    await session.execute(
        text("""
            INSERT INTO distribuidoras (id, date_gdb, dist_name) 
            VALUES (:id, :ano, :nome)
        """),
        {"id": id_real, "ano": ano_teste, "nome": nome_real}
    )
    await session.commit()
    
    return {
        "id": id_real, 
        "dist_name": nome_real, 
        "date_gdb": ano_teste
    }


@pytest_asyncio.fixture
async def setup_test_data(session, mongo_db, setup_distribuidora):
    """
    Simula um job que já passou pelo trigger e download.
    Prepara o MongoDB exatamente como a pipeline_trigger faria.
    """
    dist = setup_distribuidora
    job_id = str(uuid.uuid4())
    ano = 2024

    session.execute(
        text("UPDATE distribuidoras SET job_id = :job_id WHERE id = :id AND date_gdb = :ano"),
             {"job_id": job_id, "id": dist["id"], "ano": dist["date_gdb"]}
         )
        
    await session.commit()

    await mongo_db['jobs'].insert_one({
        "job_id": job_id,
        "distribuidora_id": dist["id"],
        "dist_name": dist["dist_name"],
        "ano_gdb": ano,
        "status": "completed",
        "created_at": datetime.utcnow()
    })

    await mongo_db['segmentos_mt_tabular'].insert_one({
        'job_id': job_id, 'COMP': 5000.0, 'CONJ': '100', 'CTMT': 'CIRC_1'
    })

    return job_id


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


@pytest.fixture(scope="session", autouse=True)
def setup_celery_test_config():
    """
    Força o Celery a usar configurações de teste, independente de
    quando as variáveis de ambiente foram setadas.
    """
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,

        broker_url="memory://",
        result_backend="cache+memory://",

        broker_connection_retry_on_startup=False,
        broker_connection_max_retries=1
    )

    yield celery_app


@pytest.fixture(autouse=True)
def mock_time_sleep():
    with patch('time.sleep'):
        yield
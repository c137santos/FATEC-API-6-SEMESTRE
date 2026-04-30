import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from httpx import AsyncClient

from backend.core.models import Distribuidora


@pytest_asyncio.fixture
async def sample_distribuidoras(session: AsyncSession):
    """Create sample distributors for testing"""
    # Clean existing data first
    await session.execute(text('DELETE FROM distribuidoras'))
    await session.commit()

    distributors = [
        Distribuidora(id='dist_001', date_gdb=2024, dist_name='CPFL Paulista'),
        Distribuidora(id='dist_002', date_gdb=2024, dist_name='EQUATORIAL'),
        Distribuidora(id='dist_003', date_gdb=2023, dist_name='AES Sul'),
    ]

    for dist in distributors:
        session.add(dist)

    await session.commit()
    return distributors


@pytest.mark.asyncio
async def test_get_distributors_with_data(
    client: AsyncClient, sample_distribuidoras
):
    """Test GET /distributors with data in database"""
    response = await client.get('/dist/distributors')

    assert response.status_code == 200
    data = response.json()

    # Should return 3 distributors
    assert len(data) == 3

    # Should be ordered by name ascending
    assert data[0]['nome'] == 'AES Sul'
    assert data[1]['nome'] == 'CPFL Paulista'
    assert data[2]['nome'] == 'EQUATORIAL'

    # Verify structure
    for distributor in data:
        assert 'id' in distributor
        assert 'nome' in distributor
        assert 'ano' in distributor
        assert isinstance(distributor['id'], str)
        assert isinstance(distributor['nome'], str)
        assert isinstance(distributor['ano'], int)


@pytest.mark.asyncio
async def test_get_distributors_empty_table(
    client: AsyncClient, session: AsyncSession
):
    """Test GET /distributors with empty table"""
    # Ensure table is empty
    await session.execute(text('DELETE FROM distribuidoras'))
    await session.commit()

    response = await client.get('/dist/distributors')

    assert response.status_code == 200
    data = response.json()

    # Should return empty list
    assert data == []


@pytest.mark.asyncio
async def test_get_distributors_database_error(
    client: AsyncClient, monkeypatch
):
    """Test GET /distributors with database connection error"""

    async def mock_execute(*args, **kwargs):
        raise Exception('Simulated database failure')

    monkeypatch.setattr(AsyncSession, 'execute', mock_execute)

    response = await client.get('/dist/distributors')

    assert response.status_code == 500
    error_data = response.json()
    assert 'detail' in error_data
    assert 'Erro interno ao buscar distribuidoras' in error_data['detail']


@pytest.mark.asyncio
async def test_get_distributors_response_structure(
    client: AsyncClient, sample_distribuidoras
):
    """Test GET /distributors response structure matches expected format"""
    response = await client.get('/dist/distributors')

    assert response.status_code == 200
    data = response.json()

    # Verify response is a list
    assert isinstance(data, list)

    if data:  # If there's data, verify structure
        distributor = data[0]
        assert isinstance(distributor, dict)
        assert 'id' in distributor
        assert 'nome' in distributor
        assert 'ano' in distributor

        # Verify field types
        assert isinstance(distributor['id'], str)
        assert isinstance(distributor['nome'], str)
        assert isinstance(distributor['ano'], int)

        # Verify specific expected values
        expected_ids = [dist.id for dist in sample_distribuidoras]
        assert distributor['id'] in expected_ids

from unittest.mock import patch, AsyncMock, MagicMock
from backend.services.render_tam import render_grafico_barras_tam

import pytest
from sqlalchemy import text


@pytest.fixture(autouse=True)
def mock_external_deps(mongo_db):
    """
    Isola o teste de dependências externas, garantindo que o Celery não seja acionado.
    """
    with patch("backend.services.pipeline_trigger.get_mongo_async_db", return_value=mongo_db), \
         patch("backend.services.etl_download.enqueue_download_gdb") as mock_enqueue, \
         patch("backend.services.pipeline_trigger.chain") as mock_chain:
        
        mock_chain.return_value.delay.return_value = MagicMock(id="mock-job-id")
        
        yield {
            "enqueue_download_gdb": mock_enqueue, 
            "chain": mock_chain
        }

        
@pytest.mark.asyncio
async def test_render_grafico_barras_tam_sucesso(monkeypatch):
    mock_data = [{
        'NOME': 'LINHA_A',
        'CTMT': '123',
        'COMP_KM': 10.5,
        'dist_name': 'ENERGISA_TESTE',
        'job_id': 'job-123'
    }]

    mock_cursor = AsyncMock()
    mock_cursor.to_list.return_value = mock_data

    mock_coll_obj = MagicMock()
    mock_coll_obj.find.return_value = mock_cursor

    monkeypatch.setattr(
        'backend.services.render_tam.get_mongo_collection',
        lambda name: mock_coll_obj
    )

    job_id = "job-123"
    caminho_gerado = await render_grafico_barras_tam(job_id)

    assert caminho_gerado.exists()
    assert f"grafico_tam_{job_id}" in caminho_gerado.name
    
    if caminho_gerado.exists():
        caminho_gerado.unlink()

@pytest.mark.asyncio
async def test_render_grafico_tam_vazio(monkeypatch):
    mock_cursor = AsyncMock()
    mock_cursor.to_list.return_value = []

    mock_coll_obj = MagicMock()
    mock_coll_obj.find.return_value = mock_cursor

    monkeypatch.setattr(
        'backend.services.render_tam.get_mongo_collection',
        lambda name: mock_coll_obj
    )

    with pytest.raises(ValueError, match="Nenhum dado encontrado"):
        await render_grafico_barras_tam("job-vazio")
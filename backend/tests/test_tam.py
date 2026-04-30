import pytest
import uuid
from backend.services.calculo_tam import calcular_extensao_tam
from core.schemas import DistributorMetadata

COLECAO_RESULTADOS = 'TAM'

@pytest.mark.asyncio
async def test_fluxo_calculo_e_leitura_real(client, mongo_db, setup_test_data):
    """
    Valida desde a entrada bruta no Mongo até a saída JSON no Endpoint.
    """
    job_id = setup_test_data

    metadata = DistributorMetadata(
        job_id=job_id, id="fake-id", dist_name="CEMIG-D", date_gdb=2024
    )
    
    segmentos = await mongo_db['segmentos_mt_tabular'].find({'job_id': job_id}).to_list(None)
    
    resultados = calcular_extensao_tam(
        metadata=metadata,
        segmentos=segmentos,
        map_circuitos={},
        map_conjuntos={'999': 'CONJUNTO 999'} 
    )

    documentos = [t.model_dump() for t in resultados]
    await mongo_db[COLECAO_RESULTADOS].insert_many(documentos)
    
    response = await client.get(f'/tam/{job_id}')
    
    assert response.status_code == 200
    data = response.json()["data"]
    
    assert data["todos_trechos"][0]["COMP_KM"] == 3.0
    assert data["todos_trechos"][0]["CONJ"] == '100'

@pytest.mark.asyncio
async def test_get_tam_not_found(client):
    """Garante que jobs inexistentes retornam 404."""
    response = await client.get(f'/tam/{uuid.uuid4()}')
    assert response.status_code == 404
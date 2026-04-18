import pytest


@pytest.mark.asyncio
async def test_get_tam_200_sucesso(client, setup_test_data):
    """Testa resposta 200 para um job_id que já existe no banco populado."""
    job_id = setup_test_data
    
    response = await client.get(f"/tam/{job_id}")
    
    assert response.status_code == 200
    assert "data" in response.json()


@pytest.mark.asyncio
async def test_get_tam_nomes_corretos(client, mongo_db, setup_test_data):
    """Valida se o nome retornado pela API bate com um dos registros do banco."""
    job_id = setup_test_data
    colecao = mongo_db["segmentos_mt_tabular"]
    
    amostra = colecao.find_one({"job_id": job_id})
    assert amostra is not None
    ctmt_alvo = amostra["CTMT"]
    
    response = await client.get(f"/tam/{job_id}")
    assert response.status_code == 200

    dados_api = response.json()["data"]["trechos"]
    item_api = next((t for t in dados_api if t["CTMT"] == ctmt_alvo), None)
    
    assert item_api is not None
    assert "NOME" in item_api
    assert len(item_api["NOME"]) > 0


@pytest.mark.asyncio
async def test_get_tam_404_job_inexistente(client):
    """Verifica 404 para um JOB_ID aleatório que não consta no banco."""
    response = await client.get("/tam/12345")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_tam_estrutura_resposta(client, setup_test_data):
    """Verifica se a estrutura da resposta JSON respeita o contrato da API."""
    job_id = setup_test_data
    response = await client.get(f"/tam/{job_id}")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "success"
    assert "metadata" in data
    assert data["metadata"]["job_id"] == job_id
    assert "trechos" in data["data"]
    assert "ranking_por_conjunto" in data["data"]
    assert "top_10" in data["data"]


@pytest.mark.asyncio
async def test_get_tam_ranking_por_conjunto(client, setup_test_data):
    """Verifica o formato das listas de ranking vindas do banco populado."""
    job_id = setup_test_data
    response = await client.get(f"/tam/{job_id}")
    
    assert response.status_code == 200
    
    response_data = response.json()
    ranking = response_data["data"]["ranking_por_conjunto"]
    top_10 = response_data["data"]["top_10"]
    
    assert isinstance(ranking, list)
    assert isinstance(top_10, list)
    assert len(top_10) <= 10


@pytest.mark.asyncio
async def test_get_tam_calculo_comp_km(client, mongo_db, setup_test_data):
    """Valida se a API está somando corretamente os comprimentos do banco."""
    job_id = setup_test_data
    colecao = mongo_db["segmentos_mt_tabular"]
    
    amostra = colecao.find_one({"job_id": job_id})
    ctmt_alvo = amostra["CTMT"]
    
    pipeline = [
        {"$match": {"job_id": job_id, "CTMT": ctmt_alvo}},
        {"$group": {"_id": "$CTMT", "total_metros": {"$sum": "$COMP"}}}
    ]
    resultado_banco = list(colecao.aggregate(pipeline))
    soma_metros = resultado_banco[0]["total_metros"]
    esperado_km = soma_metros / 1000

    response = await client.get(f"/tam/{job_id}")
    assert response.status_code == 200
    
    dados_api = response.json()["data"]["trechos"]
    item_api = next((t for t in dados_api if t["CTMT"] == ctmt_alvo), None)
    
    assert item_api is not None
    assert item_api["COMP_KM"] == pytest.approx(esperado_km, rel=1e-3)
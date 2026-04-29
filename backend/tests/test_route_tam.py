import pytest

COLECAO_RESULTADOS = 'TAM'

@pytest.mark.asyncio
async def test_get_tam_200_sucesso(client, setup_test_data):
    response = await client.get(f"/tam/{setup_test_data}")
    
    if response.status_code != 200:
        print(f"\nERRO NO BACKEND: {response.text}")
        
    assert response.status_code == 200
    data = response.json()
    
    assert data.get('status') == 'success'
    assert 'distribuidora_info' in data.get('metadata', {})


@pytest.mark.asyncio
async def test_get_tam_integracao_postgres_mongo(mongo_db, setup_test_data, client):
    response = await client.get(f"/tam/{setup_test_data}")
    assert response.status_code == 200
    
    colecao = mongo_db[COLECAO_RESULTADOS]
    documento_no_banco = await colecao.find_one({'job_id': setup_test_data})
    
    dados_api = response.json()['metadata']['distribuidora_info']
    
    assert dados_api['dist_name'] == documento_no_banco['dist_name']
    assert dados_api['id'] == documento_no_banco['id']


@pytest.mark.asyncio
async def test_get_tam_estrutura_data(client, setup_test_data):
    """Valida a estrutura JSON de retorno."""
    response = await client.get(f"/tam/{setup_test_data}")
    res_json = response.json()
    data_section = res_json.get('data', {})
    
    assert 'trechos' in data_section
    assert 'ranking_por_conjunto' in data_section
    assert 'top_10' in data_section

@pytest.mark.asyncio
async def test_get_tam_404_not_found(client):
    """Valida erro 404 para Job ID inexistente."""
    response = await client.get('/tam/job_inexistente_999')
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_tam_consistencia_calculo(mongo_db, setup_test_data, client):
    """Verifica se a contagem no Mongo bate com a lista retornada na API."""
    response = await client.get(f"/tam/{setup_test_data}")
    res_json = response.json()
    
    total_api = len(res_json['data']['trechos'])
    
    colecao = mongo_db[COLECAO_RESULTADOS]
    total_no_banco = await colecao.count_documents({'job_id': setup_test_data})
    
    assert total_api == total_no_banco
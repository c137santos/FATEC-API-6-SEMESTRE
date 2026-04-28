import pytest

COLECAO_ALVO = 'segmentos_mt_tabular'


@pytest.mark.asyncio
async def test_get_tam_200_sucesso(api_response):
    assert api_response.status_code == 200
    assert 'data' in api_response.json()


@pytest.mark.asyncio
async def test_get_tam_nomes_corretos(mongo_db, setup_test_data, api_response):
    colecao = mongo_db[COLECAO_ALVO]
    amostra = await colecao.find_one({'job_id': setup_test_data})
    assert amostra is not None
    ctmt_esperado = amostra['CTMT']

    dados_api = api_response.json()['data']['trechos']
    item_api = next((t for t in dados_api if t['CTMT'] == ctmt_esperado), None)

    assert item_api is not None
    assert 'NOME' in item_api
    assert item_api['NOME'] == ctmt_esperado, (
        f'Esperava fallback para {ctmt_esperado}, mas veio {item_api["NOME"]}'
    )


@pytest.mark.asyncio
async def test_get_tam_404_job_inexistente(client):
    response = await client.get('/tam/12345')
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_tam_estrutura_resposta(api_response, setup_test_data):
    data = api_response.json()
    assert data['metadata']['job_id'] == setup_test_data
    assert all(
        k in data['data']
        for k in ['trechos', 'ranking_por_conjunto', 'top_10']
    )


@pytest.mark.asyncio
async def test_get_tam_calculo_comp_km(
    mongo_db, setup_test_data, api_response
):
    colecao = mongo_db[COLECAO_ALVO]
    amostra = await colecao.find_one({'job_id': setup_test_data})
    ctmt_alvo = amostra['CTMT']

    pipeline = [
        {'$match': {'job_id': setup_test_data, 'CTMT': ctmt_alvo}},
        {'$group': {'_id': '$CTMT', 'total_metros': {'$sum': '$COMP'}}},
    ]
    resultado_banco = await colecao.aggregate(pipeline).to_list(length=None)
    esperado_km = resultado_banco[0]['total_metros'] / 1000

    dados_api = api_response.json()['data']['trechos']
    item_api = next((t for t in dados_api if t['CTMT'] == ctmt_alvo), None)

    assert item_api is not None
    assert item_api['COMP_KM'] == pytest.approx(esperado_km, rel=1e-3)

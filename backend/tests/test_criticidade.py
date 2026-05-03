"""
Testes automatizados para o endpoint de criticidade.
Formato funcional sem classes, seguindo as melhores práticas.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.services.criticidade import (
    calcular_desvio,
    calcular_score_criticidade,
    classificar_criticidade,
    criar_mapa_criticidade,
)

_PATCH_REALIZADOS = 'backend.services.criticidade.buscar_dados_realizados'
_PATCH_LIMITES = 'backend.services.criticidade.buscar_dados_limites'
_PATCH_SALVAR = 'backend.services.criticidade.salvar_score_criticidade'
_PATCH_COL = 'backend.services.criticidade.get_mongo_collection'
_PATCH_SCORE = 'backend.routes.criticidade.calcular_score_criticidade'

client = TestClient(app)

_DADOS_REALIZADOS = [
    {
        'sig_agente': 'EQUATORIAL',
        'ide_conj': '123',
        'dsc_conj': 'CONJ TESTE',
        'sig_indicador': 'DEC',
        'valor_realizado': 110.0,
    },
    {
        'sig_agente': 'EQUATORIAL',
        'ide_conj': '123',
        'dsc_conj': 'CONJ TESTE',
        'sig_indicador': 'FEC',
        'valor_realizado': 105.0,
    },
]

_DADOS_LIMITES = [
    {
        'sig_agente': 'EQUATORIAL',
        'ide_conj': '123',
        'dsc_conj': 'CONJ TESTE',
        'sig_indicador': 'DEC',
        'valor_limite': 100.0,
    },
    {
        'sig_agente': 'EQUATORIAL',
        'ide_conj': '123',
        'dsc_conj': 'CONJ TESTE',
        'sig_indicador': 'FEC',
        'valor_limite': 100.0,
    },
]


def test_calcular_desvio():
    """Testa função de cálculo de desvio."""
    assert calcular_desvio(110, 100) == 10.0
    assert calcular_desvio(90, 100) == 0.0
    assert calcular_desvio(100, 0) == 0.0
    assert calcular_desvio(200, 100) == 100.0
    assert abs(calcular_desvio(105.5, 100) - 5.5) < 0.001


def test_classificar_criticidade():
    """Testa função de classificação de cores."""
    assert classificar_criticidade(0) == 'Verde'
    assert classificar_criticidade(1) == 'Laranja'
    assert classificar_criticidade(5) == 'Laranja'
    assert classificar_criticidade(10) == 'Laranja'
    assert classificar_criticidade(10.1) == 'Vermelho'
    assert classificar_criticidade(50) == 'Vermelho'
    assert classificar_criticidade(375) == 'Vermelho'


def test_endpoint_criticidade_sucesso():
    """Testa endpoint com dados válidos."""
    mock_result = {
        'ano': 2024,
        'distribuidora': 'EQUATORIAL',
        'score_criticidade': 50.0,
        'desvio_dec': 25.0,
        'desvio_fec': 25.0,
        'cor': 'Vermelho',
        'quantidade_conjuntos': 5,
    }

    with patch(_PATCH_SCORE, return_value=mock_result):
        response = client.get(
            '/etl/criticidade?ano=2024&distribuidora=EQUATORIAL'
        )
        assert response.status_code == 200
        data = response.json()
        assert data['ano'] == 2024
        assert data['distribuidora'] == 'EQUATORIAL'
        assert data['score_criticidade'] == 50.0
        assert data['desvio_dec'] == 25.0
        assert data['desvio_fec'] == 25.0
        assert data['cor'] == 'Vermelho'


def test_endpoint_criticidade_ano_invalido():
    """Testa endpoint com ano inválido."""
    response = client.get('/etl/criticidade?ano=1999&distribuidora=EQUATORIAL')
    assert response.status_code == 400
    assert 'Ano deve estar entre' in response.json()['detail']


def test_endpoint_criticidade_ano_futuro():
    """Testa endpoint com ano muito futuro."""
    response = client.get('/etl/criticidade?ano=2050&distribuidora=EQUATORIAL')
    assert response.status_code == 400
    assert 'Ano deve estar entre' in response.json()['detail']


def test_endpoint_criticidade_distribuidora_curta():
    """Testa endpoint com nome de distribuidora muito curto."""
    response = client.get('/etl/criticidade?ano=2024&distribuidora=A')
    assert response.status_code == 400
    assert (
        'Nome da distribuidora deve ter pelo menos 2 caracteres'
        in response.json()['detail']
    )


def test_endpoint_criticidade_dados_nao_encontrados():
    """Testa endpoint quando não há dados para os parâmetros."""
    with patch(_PATCH_SCORE, return_value=None):
        response = client.get(
            '/etl/criticidade?ano=2024&distribuidora=INEXISTENTE'
        )
        assert response.status_code == 404
        detail = response.json()['detail']
        assert 'Dados não encontrados para distribuidora' in detail
        assert "'INEXISTENTE'" in detail
        assert '2024' in detail


def test_endpoint_criticidade_erro_interno():
    """Testa endpoint quando ocorre erro interno."""
    with patch(_PATCH_SCORE, side_effect=Exception('Erro simulado')):
        response = client.get(
            '/etl/criticidade?ano=2024&distribuidora=EQUATORIAL'
        )
        assert response.status_code == 500
        assert (
            'Erro interno ao processar solicitação'
            in response.json()['detail']
        )


def test_endpoint_criticidade_parametros_faltando():
    """Testa endpoint sem parâmetros obrigatórios."""
    response = client.get('/etl/criticidade')
    assert response.status_code == 422


def test_endpoint_criticidade_apenas_ano():
    """Testa endpoint com apenas o parâmetro ano."""
    response = client.get('/etl/criticidade?ano=2024')
    assert response.status_code == 422


def test_endpoint_criticidade_apenas_distribuidora():
    """Testa endpoint com apenas o parâmetro distribuidora."""
    response = client.get('/etl/criticidade?distribuidora=EQUATORIAL')
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_calcular_score_criticidade_sem_dados():
    """Testa função de cálculo quando não há dados."""
    with (
        patch(_PATCH_REALIZADOS, return_value=[]),
        patch(_PATCH_LIMITES, return_value=[]),
    ):
        resultado = await calcular_score_criticidade(2024, 'EQUATORIAL')
        assert resultado is None


@pytest.mark.asyncio
async def test_calcular_score_criticidade_com_dados():
    """Testa função de cálculo com dados mockados."""
    with (
        patch(_PATCH_REALIZADOS, return_value=_DADOS_REALIZADOS),
        patch(_PATCH_LIMITES, return_value=_DADOS_LIMITES),
        patch(_PATCH_SALVAR) as mock_salvar,
    ):
        resultado = await calcular_score_criticidade(2024, 'EQUATORIAL')

        assert resultado is not None
        assert resultado['ano'] == 2024
        assert resultado['distribuidora'] == 'EQUATORIAL'
        assert resultado['score_criticidade'] > 0
        assert resultado['cor'] in {'Verde', 'Laranja', 'Vermelho'}
        assert mock_salvar.called


def test_endpoint_criticidade_case_insensitive():
    """Testa se endpoint trata nome da distribuidora de forma case insensitive."""
    mock_result = {
        'ano': 2024,
        'distribuidora': 'EQUATORIAL',
        'score_criticidade': 25.0,
        'desvio_dec': 15.0,
        'desvio_fec': 10.0,
        'cor': 'Laranja',
        'quantidade_conjuntos': 3,
    }

    with patch(_PATCH_SCORE, return_value=mock_result):
        response = client.get(
            '/etl/criticidade?ano=2024&distribuidora=equatorial'
        )
        assert response.status_code == 200
        assert response.json()['distribuidora'] == 'EQUATORIAL'

        response = client.get(
            '/etl/criticidade?ano=2024&distribuidora=Equatorial'
        )
        assert response.status_code == 200
        assert response.json()['distribuidora'] == 'EQUATORIAL'


def test_endpoint_criticidade_espacos_branco():
    """Testa se endpoint trata espaços em branco no nome da distribuidora."""
    mock_result = {
        'ano': 2024,
        'distribuidora': 'EQUATORIAL',
        'score_criticidade': 0.0,
        'desvio_dec': 0.0,
        'desvio_fec': 0.0,
        'cor': 'Verde',
        'quantidade_conjuntos': 1,
    }

    with patch(_PATCH_SCORE, return_value=mock_result):
        response = client.get(
            '/etl/criticidade?ano=2024&distribuidora= EQUATORIAL '
        )
        assert response.status_code == 200
        assert response.json()['distribuidora'] == 'EQUATORIAL'


def test_classificar_criticidade_limites():
    """Testa limites exatos da função de classificação."""
    assert classificar_criticidade(10) == 'Laranja'
    assert classificar_criticidade(10.0001) == 'Vermelho'
    assert classificar_criticidade(0) == 'Verde'
    assert classificar_criticidade(0.0001) == 'Laranja'


def test_calcular_desvio_precisao():
    """Testa precisão do cálculo de desvio."""
    resultado = calcular_desvio(100.123456, 100)
    assert abs(resultado - 0.123456) < 0.000001

    resultado = calcular_desvio(1000000.5, 1000000)
    assert abs(resultado - 0.05) < 0.1


# ---------------------------------------------------------------------------
# Testes: criar_mapa_criticidade
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_criar_mapa_sem_dados_realizados():
    """Retorna None quando não há dados realizados."""
    with patch(_PATCH_REALIZADOS, return_value=[]):
        resultado = await criar_mapa_criticidade(
            'EQUATORIAL', 2024, 'dist-001'
        )
        assert resultado is None


@pytest.mark.asyncio
async def test_criar_mapa_sem_job_id():
    """Cria mapa sem job_id quando não fornecido."""
    mock_col = AsyncMock()

    with (
        patch(_PATCH_REALIZADOS, return_value=_DADOS_REALIZADOS),
        patch(_PATCH_LIMITES, return_value=_DADOS_LIMITES),
        patch(_PATCH_COL, return_value=mock_col),
    ):
        resultado = await criar_mapa_criticidade(
            'EQUATORIAL', 2024, 'dist-001'
        )

        assert resultado is not None
        assert resultado['distribuidora'] == 'EQUATORIAL'
        assert resultado['ano'] == 2024
        assert resultado['distribuidora_id'] == 'dist-001'
        assert resultado['job_id'] is None
        assert resultado['total_conjuntos'] == 1
        assert resultado['conjuntos'][0]['ide_conj'] == '123'
        mock_col.update_one.assert_called_once()


@pytest.mark.asyncio
async def test_criar_mapa_multiplos_conjuntos_ordenados_por_score():
    """Conjuntos são retornados em ordem decrescente de score."""
    realizados_multi = [
        {
            'sig_agente': 'EQUATORIAL',
            'ide_conj': '111',
            'sig_indicador': 'DEC',
            'valor_realizado': 150.0,
        },
        {
            'sig_agente': 'EQUATORIAL',
            'ide_conj': '111',
            'sig_indicador': 'FEC',
            'valor_realizado': 120.0,
        },
        {
            'sig_agente': 'EQUATORIAL',
            'ide_conj': '222',
            'sig_indicador': 'DEC',
            'valor_realizado': 102.0,
        },
        {
            'sig_agente': 'EQUATORIAL',
            'ide_conj': '222',
            'sig_indicador': 'FEC',
            'valor_realizado': 101.0,
        },
    ]
    limites_multi = [
        {
            'sig_agente': 'EQUATORIAL',
            'ide_conj': '111',
            'sig_indicador': 'DEC',
            'valor_limite': 100.0,
        },
        {
            'sig_agente': 'EQUATORIAL',
            'ide_conj': '111',
            'sig_indicador': 'FEC',
            'valor_limite': 100.0,
        },
        {
            'sig_agente': 'EQUATORIAL',
            'ide_conj': '222',
            'sig_indicador': 'DEC',
            'valor_limite': 100.0,
        },
        {
            'sig_agente': 'EQUATORIAL',
            'ide_conj': '222',
            'sig_indicador': 'FEC',
            'valor_limite': 100.0,
        },
    ]
    mock_col = AsyncMock()

    with (
        patch(_PATCH_REALIZADOS, return_value=realizados_multi),
        patch(_PATCH_LIMITES, return_value=limites_multi),
        patch(_PATCH_COL, return_value=mock_col),
    ):
        resultado = await criar_mapa_criticidade(
            'EQUATORIAL', 2024, 'dist-001'
        )

        assert resultado['total_conjuntos'] == 2
        scores = [c['score_criticidade'] for c in resultado['conjuntos']]
        assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_criar_mapa_documento_salvo_corretamente():
    """Verifica que o documento salvo no MongoDB tem os campos esperados."""
    mock_col = AsyncMock()

    with (
        patch(_PATCH_REALIZADOS, return_value=_DADOS_REALIZADOS),
        patch(_PATCH_LIMITES, return_value=_DADOS_LIMITES),
        patch(_PATCH_COL, return_value=mock_col),
    ):
        await criar_mapa_criticidade('EQUATORIAL', 2024, 'dist-001', 'job-xyz')

        call_args = mock_col.update_one.call_args[0]
        filtro, update = call_args[0], call_args[1]

        assert filtro == {'distribuidora_id': 'dist-001', 'ano': 2024}
        doc = update['$set']
        assert doc['distribuidora'] == 'EQUATORIAL'
        assert doc['ano'] == 2024
        assert doc['job_id'] == 'job-xyz'
        assert doc['distribuidora_id'] == 'dist-001'
        assert 'conjuntos' in doc
        assert 'total_conjuntos' in doc

"""
Testes automatizados para o endpoint de criticidade.
Formato funcional sem classes, seguindo as melhores práticas.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.app import app
from backend.services.criticidade import (
    calcular_desvio,
    classificar_criticidade,
    calcular_score_criticidade,
)

client = TestClient(app)


def test_calcular_desvio():
    """Testa função de cálculo de desvio."""
    # Teste com valores normais
    assert calcular_desvio(110, 100) == 10.0
    assert calcular_desvio(90, 100) == 0.0  # Não pode ser negativo

    # Teste com limite zero
    assert calcular_desvio(100, 0) == 0.0

    # Teste com valores altos
    assert calcular_desvio(200, 100) == 100.0

    # Teste com valores decimais
    assert abs(calcular_desvio(105.5, 100) - 5.5) < 0.001


def test_classificar_criticidade():
    """Testa função de classificação de cores."""
    # Teste score zero - Verde
    assert classificar_criticidade(0) == 'Verde'

    # Teste scores baixos - Laranja
    assert classificar_criticidade(1) == 'Laranja'
    assert classificar_criticidade(5) == 'Laranja'
    assert classificar_criticidade(10) == 'Laranja'

    # Teste scores altos - Vermelho
    assert classificar_criticidade(10.1) == 'Vermelho'
    assert classificar_criticidade(50) == 'Vermelho'
    assert classificar_criticidade(375) == 'Vermelho'


def test_endpoint_criticidade_sucesso():
    """Testa endpoint com dados válidos."""
    # Mock do serviço para retornar dados de exemplo
    mock_result = {
        'ano': 2024,
        'distribuidora': 'EQUATORIAL',
        'score_criticidade': 50.0,
        'desvio_dec': 25.0,
        'desvio_fec': 25.0,
        'cor': 'Vermelho',
        'quantidade_conjuntos': 5,
    }

    with patch(
        'backend.routes.criticidade.calcular_score_criticidade',
        return_value=mock_result,
    ):
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
    assert 'Ano deve estar entre 2000 e 2030' in response.json()['detail']


def test_endpoint_criticidade_ano_futuro():
    """Testa endpoint com ano muito futuro."""
    response = client.get('/etl/criticidade?ano=2050&distribuidora=EQUATORIAL')

    assert response.status_code == 400
    assert 'Ano deve estar entre 2000 e 2030' in response.json()['detail']


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
    with patch(
        'backend.routes.criticidade.calcular_score_criticidade',
        return_value=None,
    ):
        response = client.get(
            '/etl/criticidade?ano=2024&distribuidora=INEXISTENTE'
        )

        assert response.status_code == 404
        assert (
            "Dados não encontrados para distribuidora 'INEXISTENTE' no ano 2024"
            in response.json()['detail']
        )


def test_endpoint_criticidade_erro_interno():
    """Testa endpoint quando ocorre erro interno."""
    with patch(
        'backend.routes.criticidade.calcular_score_criticidade',
        side_effect=Exception('Erro simulado'),
    ):
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

    assert response.status_code == 422  # Validation error


def test_endpoint_criticidade_apenas_ano():
    """Testa endpoint com apenas o parâmetro ano."""
    response = client.get('/etl/criticidade?ano=2024')

    assert response.status_code == 422  # Validation error


def test_endpoint_criticidade_apenas_distribuidora():
    """Testa endpoint com apenas o parâmetro distribuidora."""
    response = client.get('/etl/criticidade?distribuidora=EQUATORIAL')

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_calcular_score_criticidade_sem_dados():
    """Testa função de cálculo quando não há dados."""
    with (
        patch(
            'backend.services.criticidade.buscar_dados_realizados',
            return_value=[],
        ),
        patch(
            'backend.services.criticidade.buscar_dados_limites',
            return_value=[],
        ),
    ):
        resultado = await calcular_score_criticidade(2024, 'EQUATORIAL')
        assert resultado is None


@pytest.mark.asyncio
async def test_calcular_score_criticidade_com_dados():
    """Testa função de cálculo com dados mockados."""
    # Mock dados realizados
    dados_realizados = [
        {
            'sig_agente': 'EQUATORIAL',
            'ide_conj': '123',
            'dsc_conj': 'TESTE',
            'sig_indicador': 'DEC',
            'valor_realizado': 110.0,
        },
        {
            'sig_agente': 'EQUATORIAL',
            'ide_conj': '123',
            'dsc_conj': 'TESTE',
            'sig_indicador': 'FEC',
            'valor_realizado': 105.0,
        },
    ]

    # Mock dados limites
    dados_limites = [
        {
            'sig_agente': 'EQUATORIAL',
            'ide_conj': '123',
            'dsc_conj': 'TESTE',
            'sig_indicador': 'DEC',
            'valor_limite': 100.0,
        },
        {
            'sig_agente': 'EQUATORIAL',
            'ide_conj': '123',
            'dsc_conj': 'TESTE',
            'sig_indicador': 'FEC',
            'valor_limite': 100.0,
        },
    ]

    with (
        patch(
            'backend.services.criticidade.buscar_dados_realizados',
            return_value=dados_realizados,
        ),
        patch(
            'backend.services.criticidade.buscar_dados_limites',
            return_value=dados_limites,
        ),
        patch(
            'backend.services.criticidade.salvar_score_criticidade'
        ) as mock_salvar,
    ):
        resultado = await calcular_score_criticidade(2024, 'EQUATORIAL')

        assert resultado is not None
        assert resultado['ano'] == 2024
        assert resultado['distribuidora'] == 'EQUATORIAL'
        assert resultado['score_criticidade'] > 0
        assert resultado['cor'] in ['Verde', 'Laranja', 'Vermelho']
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

    with patch(
        'backend.routes.criticidade.calcular_score_criticidade',
        return_value=mock_result,
    ):
        # Teste com minúsculas
        response = client.get(
            '/etl/criticidade?ano=2024&distribuidora=equatorial'
        )
        assert response.status_code == 200
        assert response.json()['distribuidora'] == 'EQUATORIAL'

        # Teste com mixed case
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

    with patch(
        'backend.routes.criticidade.calcular_score_criticidade',
        return_value=mock_result,
    ):
        response = client.get(
            '/etl/criticidade?ano=2024&distribuidora= EQUATORIAL '
        )
        assert response.status_code == 200
        assert response.json()['distribuidora'] == 'EQUATORIAL'


def test_endpoint_criticidade_valores_extremos():
    """Testa endpoint com valores extremos válidos."""
    mock_result = {
        'ano': 2000,
        'distribuidora': 'TEST',
        'score_criticidade': 999.99,
        'desvio_dec': 500.0,
        'desvio_fec': 499.99,
        'cor': 'Vermelho',
        'quantidade_conjuntos': 1,
    }

    with patch(
        'backend.routes.criticidade.calcular_score_criticidade',
        return_value=mock_result,
    ):
        # Teste ano mínimo
        response = client.get('/etl/criticidade?ano=2000&distribuidora=TEST')
        assert response.status_code == 200

        # Teste ano máximo
        mock_result['ano'] = 2030
        response = client.get('/etl/criticidade?ano=2030&distribuidora=TEST')
        assert response.status_code == 200


def test_classificar_criticidade_limites():
    """Testa limites exatos da função de classificação."""
    # Limite exato entre Laranja e Vermelho
    assert classificar_criticidade(10) == 'Laranja'
    assert classificar_criticidade(10.0001) == 'Vermelho'

    # Limite exato entre Verde e Laranja
    assert classificar_criticidade(0) == 'Verde'
    assert classificar_criticidade(0.0001) == 'Laranja'


def test_calcular_desvio_precisao():
    """Testa precisão do cálculo de desvio."""
    # Teste com alta precisão
    resultado = calcular_desvio(100.123456, 100)
    assert abs(resultado - 0.123456) < 0.000001

    # Teste com valores muito grandes
    resultado = calcular_desvio(1000000.5, 1000000)
    assert abs(resultado - 0.05) < 0.1

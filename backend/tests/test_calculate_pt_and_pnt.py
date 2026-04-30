from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.calculate_pt_and_pnt import (
    ENE_COLUMNS,
    PNT_COLUMNS,
    PT_COLUMNS,
    _sum_columns,
    _to_float,
    calculate_pt_pnt,
)

JOB_ID = 'job-test-123'


def _make_ctmt_record(cod_id: str, pt: float, pnt: float, ene: float) -> dict:
    record: dict = {'COD_ID': cod_id}
    record[PT_COLUMNS[0]] = pt
    for col in PT_COLUMNS[1:]:
        record[col] = 0.0
    record[PNT_COLUMNS[0]] = pnt
    for col in PNT_COLUMNS[1:]:
        record[col] = 0.0
    record[ENE_COLUMNS[0]] = ene
    for col in ENE_COLUMNS[1:]:
        record[col] = 0.0
    return record


def _make_mongo_mocks(
    ctmt_records: list[dict],
    conj_records: list[dict],
    ssdmt_docs: list[dict],
):
    mock_circuitos = MagicMock()
    mock_circuitos.find_one.return_value = {
        'job_id': JOB_ID,
        'records': ctmt_records,
    }

    mock_conjuntos = MagicMock()
    mock_conjuntos.find_one.return_value = {
        'job_id': JOB_ID,
        'records': conj_records,
    }

    mock_segmentos = MagicMock()
    mock_segmentos.find.return_value = iter(ssdmt_docs)

    _colecoes = {
        'circuitos_mt': mock_circuitos,
        'conjuntos': mock_conjuntos,
        'segmentos_mt_tabular': mock_segmentos,
    }

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: _colecoes[name]
    return mock_db


def test_inteiro():
    assert _to_float(10) == 10.0


def test_string_com_virgula():
    assert _to_float('1,5') == 1.5


def test_none_retorna_zero():
    assert _to_float(None) == 0.0


def test_string_vazia_retorna_zero():
    assert _to_float('') == 0.0


def test_string_invalida_retorna_zero():
    assert _to_float('abc') == 0.0


def test_soma_valores_presentes():
    record = {'PERD_A3a': 100.0, 'PERD_A4': 200.0}
    assert _sum_columns(record, ['PERD_A3a', 'PERD_A4']) == 300.0


def test_ignora_colunas_ausentes():
    record = {'PERD_A3a': 100.0}
    assert _sum_columns(record, ['PERD_A3a', 'PERD_A4']) == 100.0


def test_record_vazio_retorna_zero():
    assert _sum_columns({}, PT_COLUMNS) == 0.0


def _patch_mongo(mock_db):
    return patch(
        'backend.core.calculate_pt_and_pnt.get_mongo_sync_db',
        return_value=mock_db,
    )


def test_retorna_lista_com_conjunto():
    ctmt = [_make_ctmt_record('CTMT-01', pt=5000, pnt=2000, ene=100_000)]
    conj = [{'cod_id': 'CONJ-A', 'nome': 'Conjunto Alpha'}]
    ssdmt = [{'CTMT': 'CTMT-01', 'CONJ': 'CONJ-A'}]

    mock_client = _make_mongo_mocks(ctmt, conj, ssdmt)

    with _patch_mongo(mock_client):
        resultado = calculate_pt_pnt(JOB_ID)

    assert len(resultado) == 1
    item = resultado[0]
    assert item['conjunto'] == 'Conjunto Alpha'
    assert item['pt_mwh'] == round(5000 / 1000, 4)
    assert item['pnt_mwh'] == round(2000 / 1000, 4)
    assert item['energia_injetada_mwh'] == round(100_000 / 1000, 4)


def test_calcula_percentuais_corretamente():
    # PT=1000, PNT=500, total=1500 → %PT=66.67%, %PNT=33.33%
    ctmt = [_make_ctmt_record('CTMT-01', pt=1000, pnt=500, ene=10_000)]
    conj = [{'cod_id': 'CONJ-A', 'nome': 'Alpha'}]
    ssdmt = [{'CTMT': 'CTMT-01', 'CONJ': 'CONJ-A'}]

    mock_client = _make_mongo_mocks(ctmt, conj, ssdmt)

    with _patch_mongo(mock_client):
        resultado = calculate_pt_pnt(JOB_ID)

    item = resultado[0]
    assert item['pct_pt'] == pytest.approx(66.6667, rel=1e-3)
    assert item['pct_pnt'] == pytest.approx(33.3333, rel=1e-3)


def test_pct_none_quando_pt_e_pnt_zerados():
    ctmt = [_make_ctmt_record('CTMT-01', pt=0, pnt=0, ene=10_000)]
    conj = [{'cod_id': 'CONJ-A', 'nome': 'Alpha'}]
    ssdmt = [{'CTMT': 'CTMT-01', 'CONJ': 'CONJ-A'}]

    mock_client = _make_mongo_mocks(ctmt, conj, ssdmt)

    with _patch_mongo(mock_client):
        resultado = calculate_pt_pnt(JOB_ID)

    assert resultado[0]['pct_pt'] is None
    assert resultado[0]['pct_pnt'] is None


def test_agrega_multiplos_circuitos_no_mesmo_conjunto():
    ctmt = [
        _make_ctmt_record('CTMT-01', pt=1000, pnt=500, ene=10_000),
        _make_ctmt_record('CTMT-02', pt=2000, pnt=1000, ene=20_000),
    ]
    conj = [{'cod_id': 'CONJ-A', 'nome': 'Alpha'}]
    ssdmt = [
        {'CTMT': 'CTMT-01', 'CONJ': 'CONJ-A'},
        {'CTMT': 'CTMT-02', 'CONJ': 'CONJ-A'},
    ]

    mock_client = _make_mongo_mocks(ctmt, conj, ssdmt)

    with _patch_mongo(mock_client):
        resultado = calculate_pt_pnt(JOB_ID)

    assert len(resultado) == 1
    item = resultado[0]
    assert item['pt_mwh'] == round(3000 / 1000, 4)
    assert item['pnt_mwh'] == round(1500 / 1000, 4)
    assert item['energia_injetada_mwh'] == round(30_000 / 1000, 4)


def test_dois_conjuntos_distintos():
    ctmt = [
        _make_ctmt_record('CTMT-01', pt=1000, pnt=100, ene=5000),
        _make_ctmt_record('CTMT-02', pt=500, pnt=800, ene=3000),
    ]
    conj = [
        {'cod_id': 'CONJ-A', 'nome': 'Alpha'},
        {'cod_id': 'CONJ-B', 'nome': 'Beta'},
    ]
    ssdmt = [
        {'CTMT': 'CTMT-01', 'CONJ': 'CONJ-A'},
        {'CTMT': 'CTMT-02', 'CONJ': 'CONJ-B'},
    ]

    mock_client = _make_mongo_mocks(ctmt, conj, ssdmt)

    with _patch_mongo(mock_client):
        resultado = calculate_pt_pnt(JOB_ID)

    assert len(resultado) == 2
    nomes = [r['conjunto'] for r in resultado]
    assert 'Alpha' in nomes
    assert 'Beta' in nomes


def test_ordenado_por_pnt_decrescente():
    ctmt = [
        _make_ctmt_record('CTMT-01', pt=0, pnt=100, ene=1000),
        _make_ctmt_record('CTMT-02', pt=0, pnt=500, ene=1000),
    ]
    conj = [
        {'cod_id': 'CONJ-A', 'nome': 'Alpha'},
        {'cod_id': 'CONJ-B', 'nome': 'Beta'},
    ]
    ssdmt = [
        {'CTMT': 'CTMT-01', 'CONJ': 'CONJ-A'},
        {'CTMT': 'CTMT-02', 'CONJ': 'CONJ-B'},
    ]

    mock_client = _make_mongo_mocks(ctmt, conj, ssdmt)

    with _patch_mongo(mock_client):
        resultado = calculate_pt_pnt(JOB_ID)

    assert resultado[0]['conjunto'] == 'Beta'
    assert resultado[1]['conjunto'] == 'Alpha'


def test_retorna_lista_vazia_se_ctmt_nao_encontrado():
    mock_circuitos = MagicMock()
    mock_circuitos.find_one.return_value = None

    _colecoes = {'circuitos_mt': mock_circuitos}
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: _colecoes[name]

    with patch(
        'backend.core.calculate_pt_and_pnt.get_mongo_sync_db',
        return_value=mock_db,
    ):
        resultado = calculate_pt_pnt(JOB_ID)

    assert resultado == []


def test_retorna_lista_vazia_se_conj_nao_encontrado():
    mock_circuitos = MagicMock()
    mock_circuitos.find_one.return_value = {
        'job_id': JOB_ID,
        'records': [],
    }

    mock_conjuntos = MagicMock()
    mock_conjuntos.find_one.return_value = None

    _colecoes = {
        'circuitos_mt': mock_circuitos,
        'conjuntos': mock_conjuntos,
    }
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: _colecoes[name]

    with patch(
        'backend.core.calculate_pt_and_pnt.get_mongo_sync_db',
        return_value=mock_db,
    ):
        resultado = calculate_pt_pnt(JOB_ID)

    assert resultado == []


def test_usa_cod_id_como_nome_quando_nome_ausente():
    ctmt = [_make_ctmt_record('CTMT-01', pt=100, pnt=50, ene=1000)]
    conj = [{'cod_id': 'CONJ-A'}]
    ssdmt = [{'CTMT': 'CTMT-01', 'CONJ': 'CONJ-A'}]

    mock_client = _make_mongo_mocks(ctmt, conj, ssdmt)

    with _patch_mongo(mock_client):
        resultado = calculate_pt_pnt(JOB_ID)

    assert resultado[0]['conjunto'] == 'CONJ-A'


from backend.routes.pt_and_pnt import router as pt_and_pnt_router

_test_app = FastAPI()
_test_app.include_router(pt_and_pnt_router)


@pytest.fixture
def client():
    return TestClient(_test_app)


def _mock_calcular(resultados):
    return patch(
        'backend.routes.pt_and_pnt.calculate_pt_pnt',
        return_value=resultados,
    )


_RESULTADO_EXEMPLO = [
    {
        'conjunto': 'Alpha',
        'pt_mwh': 5.0,
        'pnt_mwh': 2.0,
        'energia_injetada_mwh': 100.0,
        'pct_pt': 71.4286,
        'pct_pnt': 28.5714,
    }
]


def test_retorna_200_com_dados(client):
    with _mock_calcular(_RESULTADO_EXEMPLO):
        response = client.get('/pt-pnt?job_id=abc-123')

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body['job_id'] == 'abc-123'
    assert body['total_conjuntos'] == 1
    assert body['resultados'][0]['conjunto'] == 'Alpha'


def test_retorna_404_quando_sem_dados(client):
    with _mock_calcular([]):
        response = client.get('/pt-pnt?job_id=nao-existe')

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_retorna_500_em_erro_inesperado(client):
    with patch(
        'backend.routes.pt_and_pnt.calculate_pt_pnt',
        side_effect=Exception('mongo down'),
    ):
        response = client.get('/pt-pnt?job_id=abc')

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert 'mongo down' in response.json()['detail']


def test_sem_job_id_retorna_422(client):
    response = client.get('/pt-pnt')
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

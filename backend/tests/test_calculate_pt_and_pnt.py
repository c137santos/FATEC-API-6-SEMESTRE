from unittest.mock import MagicMock, patch

import pytest

from backend.services.calculate_pt_and_pnt import (
    ENE_COLUMNS,
    PNT_COLUMNS,
    PT_COLUMNS,
    _sum_columns,
    _to_float,
    calculate_pt_pnt,
)

JOB_ID = 'job-test-123'
DIST_ID = 'dist-1'
SIG_AGENTE = 'ENERGISA MS'
ANO = 2023


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


def _make_mongo_mocks(ctmt_records, conj_records, ssdmt_docs):
    mock_circuitos = MagicMock()
    mock_circuitos.find_one.return_value = {
        'distribuidora_id': DIST_ID,
        'records': ctmt_records,
    }

    mock_conjuntos = MagicMock()
    mock_conjuntos.find_one.return_value = {
        'distribuidora_id': DIST_ID,
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


def _patch_mongo(mock_db):
    return patch(
        'backend.services.calculate_pt_and_pnt.get_mongo_sync_db',
        return_value=mock_db,
    )


def test_to_float():
    assert _to_float(10) == 10.0
    assert _to_float('1,5') == 1.5
    assert _to_float(None) == 0.0
    assert _to_float('') == 0.0
    assert _to_float('abc') == 0.0


def test_sum_columns():
    record = {'PERD_A3a': 100.0, 'PERD_A4': 200.0}
    assert _sum_columns(record, ['PERD_A3a', 'PERD_A4']) == 300.0

    record = {'PERD_A3a': 100.0}
    assert _sum_columns(record, ['PERD_A3a', 'PERD_A4']) == 100.0

    assert _sum_columns({}, PT_COLUMNS) == 0.0


def test_retorna_lista_com_conjunto():
    ctmt = [_make_ctmt_record('CTMT-01', 5000, 2000, 100_000)]
    conj = [{'cod_id': 'CONJ-A', 'nome': 'Conjunto Alpha'}]
    ssdmt = [{'CTMT': 'CTMT-01', 'CONJ': 'CONJ-A'}]

    mock_db = _make_mongo_mocks(ctmt, conj, ssdmt)

    with (
        _patch_mongo(mock_db),
        patch('backend.services.calculate_pt_and_pnt.salvar_pt_pnt'),
    ):
        resultado = calculate_pt_pnt(DIST_ID, JOB_ID, SIG_AGENTE, ANO)

    assert len(resultado) == 1
    item = resultado[0]
    assert item['conjunto'] == 'Conjunto Alpha'
    assert item['pt_mwh'] == 5.0
    assert item['pnt_mwh'] == 2.0
    assert item['energia_injetada_mwh'] == 100.0


def test_percentuais():
    ctmt = [_make_ctmt_record('CTMT-01', 1000, 500, 10_000)]
    conj = [{'cod_id': 'CONJ-A', 'nome': 'Alpha'}]
    ssdmt = [{'CTMT': 'CTMT-01', 'CONJ': 'CONJ-A'}]

    mock_db = _make_mongo_mocks(ctmt, conj, ssdmt)

    with (
        _patch_mongo(mock_db),
        patch('backend.services.calculate_pt_and_pnt.salvar_pt_pnt'),
    ):
        resultado = calculate_pt_pnt(DIST_ID, JOB_ID, SIG_AGENTE, ANO)

    item = resultado[0]
    assert item['pct_pt'] == pytest.approx(66.6667, rel=1e-3)
    assert item['pct_pnt'] == pytest.approx(33.3333, rel=1e-3)


def test_pct_none():
    ctmt = [_make_ctmt_record('CTMT-01', 0, 0, 10_000)]
    conj = [{'cod_id': 'CONJ-A'}]
    ssdmt = [{'CTMT': 'CTMT-01', 'CONJ': 'CONJ-A'}]

    mock_db = _make_mongo_mocks(ctmt, conj, ssdmt)

    with (
        _patch_mongo(mock_db),
        patch('backend.services.calculate_pt_and_pnt.salvar_pt_pnt'),
    ):
        resultado = calculate_pt_pnt(DIST_ID, JOB_ID, SIG_AGENTE, ANO)

    assert resultado[0]['pct_pt'] is None
    assert resultado[0]['pct_pnt'] is None


def test_agregacao():
    ctmt = [
        _make_ctmt_record('CTMT-01', 1000, 500, 10_000),
        _make_ctmt_record('CTMT-02', 2000, 1000, 20_000),
    ]
    conj = [{'cod_id': 'CONJ-A', 'nome': 'Alpha'}]
    ssdmt = [
        {'CTMT': 'CTMT-01', 'CONJ': 'CONJ-A'},
        {'CTMT': 'CTMT-02', 'CONJ': 'CONJ-A'},
    ]

    mock_db = _make_mongo_mocks(ctmt, conj, ssdmt)

    with (
        _patch_mongo(mock_db),
        patch('backend.services.calculate_pt_and_pnt.salvar_pt_pnt'),
    ):
        resultado = calculate_pt_pnt(DIST_ID, JOB_ID, SIG_AGENTE, ANO)

    item = resultado[0]
    assert item['pt_mwh'] == 3.0
    assert item['pnt_mwh'] == 1.5


def test_ordenacao():
    ctmt = [
        _make_ctmt_record('CTMT-01', 0, 100, 1000),
        _make_ctmt_record('CTMT-02', 0, 500, 1000),
    ]
    conj = [
        {'cod_id': 'CONJ-A', 'nome': 'Alpha'},
        {'cod_id': 'CONJ-B', 'nome': 'Beta'},
    ]
    ssdmt = [
        {'CTMT': 'CTMT-01', 'CONJ': 'CONJ-A'},
        {'CTMT': 'CTMT-02', 'CONJ': 'CONJ-B'},
    ]

    mock_db = _make_mongo_mocks(ctmt, conj, ssdmt)

    with (
        _patch_mongo(mock_db),
        patch('backend.services.calculate_pt_and_pnt.salvar_pt_pnt'),
    ):
        resultado = calculate_pt_pnt(DIST_ID, JOB_ID, SIG_AGENTE, ANO)

    assert resultado[0]['conjunto'] == 'Beta'


def test_lista_vazia():
    mock_db = MagicMock()
    mock_db.__getitem__.return_value.find_one.return_value = None

    with _patch_mongo(mock_db):
        resultado = calculate_pt_pnt(DIST_ID, JOB_ID, SIG_AGENTE, ANO)

    assert resultado == []
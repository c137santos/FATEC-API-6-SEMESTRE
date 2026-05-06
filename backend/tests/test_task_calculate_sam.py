"""Testes da task task_calculate_sam e da função calculate_sam."""

from unittest.mock import MagicMock, patch

import pytest

from backend.services.calculate_sam import (
    _to_float,
    calculate_sam,
)
from backend.tasks.task_calculate_sam import task_calculate_sam

TASK_MODULE = 'backend.tasks.task_calculate_sam'
CORE_MODULE = 'backend.services.calculate_sam'

JOB_ID = 'job-sam-123'
DIST_ID = 'dist-456'
SIG_AGENTE = 'ENERGISA MS'
ANO = 2023


@pytest.fixture(autouse=True)
def _mock_retry():
    with patch.object(
        task_calculate_sam,
        'retry',
        side_effect=Exception('retry triggered'),
    ):
        task_calculate_sam.push_request()
        yield
        task_calculate_sam.pop_request()


@pytest.fixture
def mock_mongo_completed():
    mock_db = MagicMock()
    mock_db['jobs'].find_one.return_value = {
        'job_id': JOB_ID,
        'status': 'completed',
    }
    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=mock_db):
        yield mock_db


@pytest.fixture
def mock_mongo_pending():
    mock_db = MagicMock()
    mock_db['jobs'].find_one.return_value = {
        'job_id': JOB_ID,
        'status': 'processing',
    }
    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=mock_db):
        yield mock_db


@pytest.fixture
def mock_mongo_no_job():
    mock_db = MagicMock()
    mock_db['jobs'].find_one.return_value = None
    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=mock_db):
        yield mock_db


def test_retorna_status_done_quando_etl_completo(mock_mongo_completed):
    with patch(f'{CORE_MODULE}.get_mongo_sync_db', return_value=MagicMock()):
        with patch(f'{CORE_MODULE}.salvar_sam'):
            result = task_calculate_sam.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert result['status'] == 'done'
    assert result['job_id'] == JOB_ID


def test_chama_calculate_sam_com_parametros_corretos(mock_mongo_completed):
    mock_db = MagicMock()
    mock_db.segmentos_mt_tabular.find.return_value = iter([])
    mock_db.unsemt.find.return_value = iter([])
    mock_db.dec_fec_realizado.find.return_value = iter([])
    mock_db.dec_fec_limite.find.return_value = iter([])
    mock_db.conjuntos.find_one.return_value = {'records': []}

    with (
        patch(f'{CORE_MODULE}.get_mongo_sync_db', return_value=mock_db),
        patch(f'{CORE_MODULE}.salvar_sam') as mock_save,
    ):
        task_calculate_sam.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    mock_save.assert_called_once_with(
        distribuidora_id=DIST_ID,
        job_id=JOB_ID,
        sig_agente=SIG_AGENTE,
        ano_indice=ANO,
        records=[],
    )


def test_dispara_retry_quando_job_ainda_processando(mock_mongo_pending):
    with pytest.raises(Exception, match='retry triggered'):
        task_calculate_sam.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)


def test_dispara_retry_quando_job_nao_encontrado(mock_mongo_no_job):
    with pytest.raises(Exception, match='retry triggered'):
        task_calculate_sam.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)


def test_nao_chama_calculate_sam_antes_do_etl_completar(mock_mongo_pending):
    with (
        patch(f'{CORE_MODULE}.get_mongo_sync_db') as mock_core_db,
        pytest.raises(Exception, match='retry triggered'),
    ):
        task_calculate_sam.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    mock_core_db.assert_not_called()


def test_propaga_excecao_do_calculate_sam(mock_mongo_completed):
    with (
        patch(
            f'{CORE_MODULE}.get_mongo_sync_db',
            side_effect=RuntimeError('mongo down'),
        ),
        pytest.raises(RuntimeError, match='mongo down'),
    ):
        task_calculate_sam.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)


def test_to_float_inteiro():
    assert _to_float(10) == 10.0


def test_to_float_string_com_virgula():
    assert _to_float('1,5') == 1.5


def test_to_float_none_retorna_none():
    assert _to_float(None) is None


def test_to_float_string_vazia_retorna_none():
    assert _to_float('') is None


def test_to_float_string_invalida_retorna_none():
    assert _to_float('abc') is None


def _make_mongo_mocks(
    segmentos: list[dict],
    unsemt: list[dict],
    dec_fec_realizado: list[dict],
    dec_fec_limite: list[dict],
    conj_records: list[dict],
) -> MagicMock:
    mock_db = MagicMock()

    mock_db.segmentos_mt_tabular.find.return_value = iter(segmentos)
    mock_db.unsemt.find.return_value = iter(unsemt)
    mock_db.dec_fec_realizado.find.return_value = iter(dec_fec_realizado)
    mock_db.dec_fec_limite.find.return_value = iter(dec_fec_limite)
    mock_db.conjuntos.find_one.return_value = {'records': conj_records}

    return mock_db


def _patch_mongo(mock_db):
    return patch(f'{CORE_MODULE}.get_mongo_sync_db', return_value=mock_db)


def test_calcula_sam_basico():
    segmentos = [{'CONJ': 'C1', 'COMP': '2000'}]
    unsemt = [{'conj': 'C1', 'coordinates': [1, 2]}]
    dec_r = [{'ide_conj': 'C1', 'sig_indicador': 'DEC', 'vlr_indice': 12.0}]
    dec_l = [{'ide_conj': 'C1', 'sig_indicador': 'DEC', 'vlr_limite': 10.0}]
    fec_r = [{'ide_conj': 'C1', 'sig_indicador': 'FEC', 'vlr_indice': 0.0}]
    fec_l = [{'ide_conj': 'C1', 'sig_indicador': 'FEC', 'vlr_limite': 5.0}]
    conj = [{'cod_id': 'C1', 'nome': 'Conjunto 1'}]

    mock_db = _make_mongo_mocks(
        segmentos, unsemt, dec_r + fec_r, dec_l + fec_l, conj
    )

    with (
        _patch_mongo(mock_db),
        patch(f'{CORE_MODULE}.salvar_sam'),
    ):
        resultado = calculate_sam(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert len(resultado) == 1
    item = resultado[0]
    assert item['conjunto'] == 'C1'
    assert item['nome'] == 'Conjunto 1'
    assert item['comp_km'] == pytest.approx(2.0)
    assert item['qtde_religadores'] == 1
    assert item['desvio_dec'] == pytest.approx(20.0)
    assert item['desvio_fec'] == pytest.approx(0.0)
    assert item['score_criticidade'] == pytest.approx(20.0)
    assert item['sam_km'] == pytest.approx(0.4)


def test_sem_religadores_usa_divisor_1():
    segmentos = [{'CONJ': 'C1', 'COMP': '1000'}]
    dec_r = [{'ide_conj': 'C1', 'sig_indicador': 'DEC', 'vlr_indice': 20.0}]
    dec_l = [{'ide_conj': 'C1', 'sig_indicador': 'DEC', 'vlr_limite': 10.0}]

    mock_db = _make_mongo_mocks(segmentos, [], dec_r, dec_l, [])

    with (
        _patch_mongo(mock_db),
        patch(f'{CORE_MODULE}.salvar_sam'),
    ):
        resultado = calculate_sam(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert resultado[0]['qtde_religadores'] == 0
    assert resultado[0]['sam_km'] == pytest.approx(1.0)


def test_desvio_negativo_vira_zero():
    segmentos = [{'CONJ': 'C1', 'COMP': '1000'}]
    dec_r = [{'ide_conj': 'C1', 'sig_indicador': 'DEC', 'vlr_indice': 5.0}]
    dec_l = [{'ide_conj': 'C1', 'sig_indicador': 'DEC', 'vlr_limite': 10.0}]

    mock_db = _make_mongo_mocks(segmentos, [], dec_r, dec_l, [])

    with (
        _patch_mongo(mock_db),
        patch(f'{CORE_MODULE}.salvar_sam'),
    ):
        resultado = calculate_sam(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert resultado[0]['desvio_dec'] == pytest.approx(0.0)
    assert resultado[0]['sam_km'] == pytest.approx(0.0)


def test_sem_limite_desvio_zero():
    segmentos = [{'CONJ': 'C1', 'COMP': '1000'}]
    dec_r = [{'ide_conj': 'C1', 'sig_indicador': 'DEC', 'vlr_indice': 15.0}]

    mock_db = _make_mongo_mocks(segmentos, [], dec_r, [], [])

    with (
        _patch_mongo(mock_db),
        patch(f'{CORE_MODULE}.salvar_sam'),
    ):
        resultado = calculate_sam(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert resultado[0]['dec_limite'] is None
    assert resultado[0]['desvio_dec'] == pytest.approx(0.0)


def test_ordenado_por_sam_km_decrescente():
    segmentos = [
        {'CONJ': 'C1', 'COMP': '1000'},
        {'CONJ': 'C2', 'COMP': '1000'},
    ]
    dec_r = [
        {'ide_conj': 'C1', 'sig_indicador': 'DEC', 'vlr_indice': 11.0},
        {'ide_conj': 'C2', 'sig_indicador': 'DEC', 'vlr_indice': 20.0},
    ]
    dec_l = [
        {'ide_conj': 'C1', 'sig_indicador': 'DEC', 'vlr_limite': 10.0},
        {'ide_conj': 'C2', 'sig_indicador': 'DEC', 'vlr_limite': 10.0},
    ]
    conj = [
        {'cod_id': 'C1', 'nome': 'Alpha'},
        {'cod_id': 'C2', 'nome': 'Beta'},
    ]

    mock_db = _make_mongo_mocks(segmentos, [], dec_r, dec_l, conj)

    with (
        _patch_mongo(mock_db),
        patch(f'{CORE_MODULE}.salvar_sam'),
    ):
        resultado = calculate_sam(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert resultado[0]['conjunto'] == 'C2'
    assert resultado[1]['conjunto'] == 'C1'


def test_retorna_lista_vazia_sem_segmentos():
    mock_db = _make_mongo_mocks([], [], [], [], [])

    with (
        _patch_mongo(mock_db),
        patch(f'{CORE_MODULE}.salvar_sam'),
    ):
        resultado = calculate_sam(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert resultado == []


def test_chama_salvar_sam_ao_final():
    segmentos = [{'CONJ': 'C1', 'COMP': '1000'}]
    mock_db = _make_mongo_mocks(segmentos, [], [], [], [])

    with (
        _patch_mongo(mock_db),
        patch(f'{CORE_MODULE}.salvar_sam') as mock_save,
    ):
        calculate_sam(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    mock_save.assert_called_once_with(
        distribuidora_id=DIST_ID,
        job_id=JOB_ID,
        sig_agente=SIG_AGENTE,
        ano_indice=ANO,
        records=mock_save.call_args.kwargs['records'],
    )


def test_multiplos_religadores_contados_por_coordenada_unica():
    segmentos = [{'CONJ': 'C1', 'COMP': '1000'}]
    unsemt = [
        {'conj': 'C1', 'coordinates': [1, 2]},
        {'conj': 'C1', 'coordinates': [3, 4]},
        {'conj': 'C1', 'coordinates': [1, 2]},
    ]
    mock_db = _make_mongo_mocks(segmentos, unsemt, [], [], [])

    with (
        _patch_mongo(mock_db),
        patch(f'{CORE_MODULE}.salvar_sam'),
    ):
        resultado = calculate_sam(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert resultado[0]['qtde_religadores'] == 2


def test_usa_conj_como_nome_quando_nao_encontrado_em_conjuntos():
    segmentos = [{'CONJ': 'C99', 'COMP': '500'}]
    mock_db = _make_mongo_mocks(segmentos, [], [], [], [])

    with (
        _patch_mongo(mock_db),
        patch(f'{CORE_MODULE}.salvar_sam'),
    ):
        resultado = calculate_sam(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert resultado[0]['nome'] == 'C99'

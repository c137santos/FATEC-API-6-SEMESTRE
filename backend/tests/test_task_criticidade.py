import pytest
from unittest.mock import MagicMock, patch
from celery.exceptions import Retry

from backend.tasks.task_criticidade import (
    _calcular_desvio,
    _classificar_criticidade,
    task_mapa_criticidade,
    task_score_criticidade,
)

PATCH_DB = 'backend.tasks.task_criticidade.get_mongo_sync_db'

_REALIZADOS = [
    {
        'sig_agente': 'ENEL RJ',
        'ide_conj': '100',
        'dsc_conj': 'CONJ A',
        'sig_indicador': 'DEC',
        'valor_realizado': 15.0,
    },
    {
        'sig_agente': 'ENEL RJ',
        'ide_conj': '100',
        'dsc_conj': 'CONJ A',
        'sig_indicador': 'FEC',
        'valor_realizado': 12.0,
    },
]

_LIMITES = [
    {
        'sig_agente': 'ENEL RJ',
        'ide_conj': '100',
        'dsc_conj': 'CONJ A',
        'sig_indicador': 'DEC',
        'valor_limite': 10.0,
    },
    {
        'sig_agente': 'ENEL RJ',
        'ide_conj': '100',
        'dsc_conj': 'CONJ A',
        'sig_indicador': 'FEC',
        'valor_limite': 10.0,
    },
]


def _make_db(job=None, realizados=None, limites=None):
    db = MagicMock()
    jobs_col = MagicMock()
    jobs_col.find_one.return_value = job
    dec_fec_r = MagicMock()
    dec_fec_r.aggregate.return_value = realizados if realizados is not None else []
    dec_fec_l = MagicMock()
    dec_fec_l.aggregate.return_value = limites if limites is not None else []
    score_col = MagicMock()
    mapa_col = MagicMock()

    def _getitem(name):
        return {
            'jobs': jobs_col,
            'dec_fec_realizado': dec_fec_r,
            'dec_fec_limite': dec_fec_l,
            'score_criticidade': score_col,
            'mapa_criticidade': mapa_col,
        }.get(name, MagicMock())

    db.__getitem__.side_effect = _getitem
    return db


# ---------------------------------------------------------------------------
# _calcular_desvio
# ---------------------------------------------------------------------------


def test_calcular_desvio_acima_do_limite():
    assert _calcular_desvio(110, 100) == pytest.approx(10.0)


def test_calcular_desvio_abaixo_do_limite_retorna_zero():
    assert _calcular_desvio(90, 100) == 0.0


def test_calcular_desvio_igual_ao_limite_retorna_zero():
    assert _calcular_desvio(100, 100) == 0.0


def test_calcular_desvio_limite_zero_retorna_zero():
    assert _calcular_desvio(50, 0) == 0.0


def test_calcular_desvio_percentual_correto():
    # DEC: (15-10)/10 * 100 = 50%
    assert _calcular_desvio(15.0, 10.0) == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# _classificar_criticidade
# ---------------------------------------------------------------------------


def test_classificar_criticidade_score_zero_e_verde():
    assert _classificar_criticidade(0) == 'Verde'


def test_classificar_criticidade_score_baixo_e_laranja():
    assert _classificar_criticidade(0.001) == 'Laranja'
    assert _classificar_criticidade(5) == 'Laranja'
    assert _classificar_criticidade(10) == 'Laranja'


def test_classificar_criticidade_acima_de_dez_e_vermelho():
    assert _classificar_criticidade(10.001) == 'Vermelho'
    assert _classificar_criticidade(500) == 'Vermelho'


# ---------------------------------------------------------------------------
# task_score_criticidade
# ---------------------------------------------------------------------------


def test_task_score_criticidade_retry_quando_job_nao_existe():
    db = _make_db(job=None)
    with patch(PATCH_DB, return_value=db):
        with pytest.raises(Retry):
            task_score_criticidade.run('job-1', 'ENEL RJ', 2024)


def test_task_score_criticidade_retry_quando_job_pendente():
    db = _make_db(job={'job_id': 'job-1', 'status': 'running'})
    with patch(PATCH_DB, return_value=db):
        with pytest.raises(Retry):
            task_score_criticidade.run('job-1', 'ENEL RJ', 2024)


def test_task_score_criticidade_sem_realizados_retorna_skipped():
    db = _make_db(job={'status': 'completed'}, realizados=[], limites=[])
    with patch(PATCH_DB, return_value=db):
        result = task_score_criticidade.run('job-1', 'ENEL RJ', 2024)
    assert result['status'] == 'skipped'
    assert result['reason'] == 'no_data'


def test_task_score_criticidade_sem_dados_completos_retorna_skipped():
    """Realizados sem correspondente em limites → nenhum conjunto completo."""
    realizados = [
        {'sig_agente': 'ENEL RJ', 'ide_conj': '100', 'sig_indicador': 'DEC', 'valor_realizado': 15.0}
    ]
    limites = [
        {'sig_agente': 'ENEL RJ', 'ide_conj': '999', 'sig_indicador': 'DEC', 'valor_limite': 10.0}
    ]
    db = _make_db(job={'status': 'completed'}, realizados=realizados, limites=limites)
    with patch(PATCH_DB, return_value=db):
        result = task_score_criticidade.run('job-1', 'ENEL RJ', 2024)
    assert result['status'] == 'skipped'
    assert result['reason'] == 'no_complete_data'


def test_task_score_criticidade_happy_path():
    db = _make_db(job={'status': 'completed'}, realizados=_REALIZADOS, limites=_LIMITES)
    with patch(PATCH_DB, return_value=db):
        result = task_score_criticidade.run('job-1', 'ENEL RJ', 2024)
    assert result['status'] == 'done'
    assert result['job_id'] == 'job-1'
    assert result['score'] > 0


def test_task_score_criticidade_score_calculado_corretamente():
    """DEC: 50%, FEC: 20% → score médio = 70."""
    realizados = [
        {'sig_agente': 'DIST', 'ide_conj': '1', 'sig_indicador': 'DEC', 'valor_realizado': 15.0},
        {'sig_agente': 'DIST', 'ide_conj': '1', 'sig_indicador': 'FEC', 'valor_realizado': 12.0},
    ]
    limites = [
        {'sig_agente': 'DIST', 'ide_conj': '1', 'sig_indicador': 'DEC', 'valor_limite': 10.0},
        {'sig_agente': 'DIST', 'ide_conj': '1', 'sig_indicador': 'FEC', 'valor_limite': 10.0},
    ]
    db = _make_db(job={'status': 'completed'}, realizados=realizados, limites=limites)
    with patch(PATCH_DB, return_value=db):
        result = task_score_criticidade.run('job-1', 'DIST', 2024)
    assert result['score'] == pytest.approx(70.0)


def test_task_score_criticidade_upsert_com_campos_corretos():
    db = _make_db(job={'status': 'completed'}, realizados=_REALIZADOS, limites=_LIMITES)
    with patch(PATCH_DB, return_value=db):
        task_score_criticidade.run('job-1', 'ENEL RJ', 2024)

    score_col = db['score_criticidade']
    score_col.update_one.assert_called_once()
    filter_arg, update_arg = score_col.update_one.call_args[0]
    assert filter_arg == {'ano': 2024, 'distribuidora': 'ENEL RJ'}
    doc = update_arg['$set']
    assert doc['distribuidora'] == 'ENEL RJ'
    assert doc['ano'] == 2024
    assert doc['quantidade_conjuntos'] == 1
    assert doc['cor'] in ('Verde', 'Laranja', 'Vermelho')


def test_task_score_criticidade_abaixo_do_limite_score_zero():
    """Realizados abaixo do limite → desvio 0 → score Verde."""
    realizados = [
        {'sig_agente': 'DIST', 'ide_conj': '1', 'sig_indicador': 'DEC', 'valor_realizado': 5.0},
        {'sig_agente': 'DIST', 'ide_conj': '1', 'sig_indicador': 'FEC', 'valor_realizado': 3.0},
    ]
    limites = [
        {'sig_agente': 'DIST', 'ide_conj': '1', 'sig_indicador': 'DEC', 'valor_limite': 10.0},
        {'sig_agente': 'DIST', 'ide_conj': '1', 'sig_indicador': 'FEC', 'valor_limite': 10.0},
    ]
    db = _make_db(job={'status': 'completed'}, realizados=realizados, limites=limites)
    with patch(PATCH_DB, return_value=db):
        result = task_score_criticidade.run('job-1', 'DIST', 2024)
    assert result['score'] == pytest.approx(0.0)
    assert db['score_criticidade'].update_one.call_args[0][1]['$set']['cor'] == 'Verde'


# ---------------------------------------------------------------------------
# task_mapa_criticidade
# ---------------------------------------------------------------------------


def test_task_mapa_criticidade_retry_quando_job_nao_completado():
    db = _make_db(job={'status': 'processing'})
    with patch(PATCH_DB, return_value=db):
        with pytest.raises(Retry):
            task_mapa_criticidade.run('job-1', 'dist-001', 'ENEL RJ', 2024)


def test_task_mapa_criticidade_sem_realizados_retorna_skipped():
    db = _make_db(job={'status': 'completed'}, realizados=[])
    with patch(PATCH_DB, return_value=db):
        result = task_mapa_criticidade.run('job-1', 'dist-001', 'ENEL RJ', 2024)
    assert result['status'] == 'skipped'
    assert result['reason'] == 'no_data'


def test_task_mapa_criticidade_happy_path():
    db = _make_db(job={'status': 'completed'}, realizados=_REALIZADOS, limites=_LIMITES)
    with patch(PATCH_DB, return_value=db):
        result = task_mapa_criticidade.run('job-1', 'dist-001', 'ENEL RJ', 2024)
    assert result['status'] == 'done'
    assert result['total_conjuntos'] == 1

    _, update_arg = db['mapa_criticidade'].update_one.call_args[0]
    doc = update_arg['$set']
    assert doc['distribuidora'] == 'ENEL RJ'
    assert doc['ano'] == 2024
    assert doc['job_id'] == 'job-1'
    assert doc['distribuidora_id'] == 'dist-001'
    assert len(doc['conjuntos']) == 1


def test_task_mapa_criticidade_conjuntos_ordenados_por_score_desc():
    realizados = [
        {'sig_agente': 'DIST', 'ide_conj': '100', 'sig_indicador': 'DEC', 'valor_realizado': 11.0},
        {'sig_agente': 'DIST', 'ide_conj': '100', 'sig_indicador': 'FEC', 'valor_realizado': 10.0},
        {'sig_agente': 'DIST', 'ide_conj': '200', 'sig_indicador': 'DEC', 'valor_realizado': 50.0},
        {'sig_agente': 'DIST', 'ide_conj': '200', 'sig_indicador': 'FEC', 'valor_realizado': 50.0},
    ]
    limites = [
        {'sig_agente': 'DIST', 'ide_conj': '100', 'sig_indicador': 'DEC', 'valor_limite': 10.0},
        {'sig_agente': 'DIST', 'ide_conj': '100', 'sig_indicador': 'FEC', 'valor_limite': 10.0},
        {'sig_agente': 'DIST', 'ide_conj': '200', 'sig_indicador': 'DEC', 'valor_limite': 10.0},
        {'sig_agente': 'DIST', 'ide_conj': '200', 'sig_indicador': 'FEC', 'valor_limite': 10.0},
    ]
    db = _make_db(job={'status': 'completed'}, realizados=realizados, limites=limites)
    with patch(PATCH_DB, return_value=db):
        task_mapa_criticidade.run('job-1', 'dist-001', 'DIST', 2024)

    _, update_arg = db['mapa_criticidade'].update_one.call_args[0]
    scores = [c['score_criticidade'] for c in update_arg['$set']['conjuntos']]
    assert scores == sorted(scores, reverse=True)


def test_task_mapa_criticidade_categoria_vermelho_quando_score_alto():
    realizados = [
        {'sig_agente': 'DIST', 'ide_conj': '1', 'sig_indicador': 'DEC', 'valor_realizado': 15.0},
        {'sig_agente': 'DIST', 'ide_conj': '1', 'sig_indicador': 'FEC', 'valor_realizado': 10.0},
    ]
    limites = [
        {'sig_agente': 'DIST', 'ide_conj': '1', 'sig_indicador': 'DEC', 'valor_limite': 10.0},
        {'sig_agente': 'DIST', 'ide_conj': '1', 'sig_indicador': 'FEC', 'valor_limite': 10.0},
    ]
    db = _make_db(job={'status': 'completed'}, realizados=realizados, limites=limites)
    with patch(PATCH_DB, return_value=db):
        task_mapa_criticidade.run('job-1', 'dist-001', 'DIST', 2024)

    _, update_arg = db['mapa_criticidade'].update_one.call_args[0]
    assert update_arg['$set']['conjuntos'][0]['categoria'] == 'Vermelho'


def test_task_mapa_criticidade_sem_limite_usa_zero():
    """Quando não há limite para um indicador, desvio é 0 (não quebra)."""
    realizados = [
        {'sig_agente': 'DIST', 'ide_conj': '1', 'sig_indicador': 'DEC', 'valor_realizado': 15.0},
    ]
    limites = []  # sem limite correspondente
    db = _make_db(job={'status': 'completed'}, realizados=realizados, limites=limites)
    with patch(PATCH_DB, return_value=db):
        result = task_mapa_criticidade.run('job-1', 'dist-001', 'DIST', 2024)
    assert result['status'] == 'done'
    _, update_arg = db['mapa_criticidade'].update_one.call_args[0]
    assert update_arg['$set']['conjuntos'][0]['desvio_dec'] == 0.0

import pytest
from unittest.mock import MagicMock, patch

from backend.tasks.task_render_tam import task_render_grafico_tam

TASK_MODULE = 'backend.tasks.task_render_tam'
JOB_ID = 'job-tam-abc'

_DADOS = [
    {'NOME': 'CIRC_A', 'CTMT': 'C1', 'COMP_KM': 10.5, 'dist_name': 'ENEL'},
    {'NOME': 'CIRC_B', 'CTMT': 'C2', 'COMP_KM': 8.0,  'dist_name': 'ENEL'},
    {'NOME': None,     'CTMT': 'C3', 'COMP_KM': 3.2,  'dist_name': 'ENEL'},
]


def _make_db(dados=None):
    if dados is None:
        dados = _DADOS
    tam_col = MagicMock()
    tam_col.find.return_value = dados
    jobs_col = MagicMock()

    db = MagicMock()

    def _getitem(name):
        return {
            'TAM': tam_col,
            'jobs': jobs_col,
        }.get(name, MagicMock())

    db.__getitem__.side_effect = _getitem
    return db


# ---------------------------------------------------------------------------
# retry
# ---------------------------------------------------------------------------


def test_render_tam_levanta_runtime_error_quando_dados_ausentes():
    db = _make_db(dados=[])
    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(f'{TASK_MODULE}.MAX_WAIT_RETRIES', 0),
    ):
        with pytest.raises(RuntimeError):
            task_render_grafico_tam.run(JOB_ID)


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------


def test_render_tam_retorna_done_quando_sucesso(tmp_path):
    db = _make_db()
    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(f'{TASK_MODULE}._output_dir', return_value=tmp_path),
    ):
        result = task_render_grafico_tam.run(JOB_ID)

    assert result['status'] == 'done'
    assert result['job_id'] == JOB_ID


def test_render_tam_path_contem_job_id(tmp_path):
    db = _make_db()
    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(f'{TASK_MODULE}._output_dir', return_value=tmp_path),
    ):
        result = task_render_grafico_tam.run(JOB_ID)

    assert JOB_ID in result['path']
    assert result['path'].endswith('.png')


def test_render_tam_nome_nulo_usa_ctmt_como_fallback(tmp_path):
    """Registro com NOME=None deve usar CTMT no eixo X sem quebrar."""
    db = _make_db()
    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(f'{TASK_MODULE}._output_dir', return_value=tmp_path),
    ):
        result = task_render_grafico_tam.run(JOB_ID)

    assert result['status'] == 'done'


# ---------------------------------------------------------------------------
# RF-1: persistência em jobs.render_paths
# ---------------------------------------------------------------------------


def test_render_tam_persiste_path_no_mongo_ao_concluir(tmp_path):
    db = _make_db()
    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(f'{TASK_MODULE}._output_dir', return_value=tmp_path),
    ):
        result = task_render_grafico_tam.run(JOB_ID)

    db['jobs'].update_one.assert_called_once_with(
        {'job_id': JOB_ID},
        {'$set': {'render_paths.grafico_tam': result['path']}},
    )


def test_render_tam_nao_persiste_quando_dados_ausentes():
    """RuntimeError antes do plot — update_one não deve ser chamado."""
    db = _make_db(dados=[])
    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(f'{TASK_MODULE}.MAX_WAIT_RETRIES', 0),
    ):
        with pytest.raises(RuntimeError):
            task_render_grafico_tam.run(JOB_ID)

    db['jobs'].update_one.assert_not_called()

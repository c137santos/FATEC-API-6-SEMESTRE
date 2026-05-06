import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.tasks.task_render_sam import task_render_sam

TASK_MODULE = 'backend.tasks.task_render_sam'
JOB_ID = 'aabbccdd-1122-3344-5566-778899001122'
DIST_ID = 'dist-render-sam-test'
SIG_AGENTE = 'EMS'
ANO = 2023

_DOC_BASE = {
    'job_id': JOB_ID,
    'distribuidora_id': DIST_ID,
    'sig_agente': SIG_AGENTE,
    'ano_indice': ANO,
    'processed_at': '2026-04-30T20:00:00+00:00',
    'records': [
        {
            'conjunto': f'C{i:03d}',
            'nome': f'Conjunto {i}',
            'sam_km': round(10.0 - i * 0.4, 4),
            'comp_km': 2.0,
            'qtde_religadores': 2,
            'dec_realizado': 12.0,
            'fec_realizado': 6.0,
            'dec_limite': 10.0,
            'fec_limite': 5.0,
            'desvio_dec': 20.0,
            'desvio_fec': 20.0,
            'score_criticidade': 40.0,
        }
        for i in range(5)
    ],
}


@pytest.fixture
def local_tmp_path():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture(autouse=True)
def _mock_retry():
    with patch.object(
        task_render_sam,
        'retry',
        side_effect=Exception('retry triggered'),
    ):
        task_render_sam.push_request()
        yield
        task_render_sam.pop_request()


@pytest.fixture
def mock_mongo_com_doc():
    mock_db = MagicMock()
    mock_db['sam_resultados'].find_one.return_value = dict(_DOC_BASE)
    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=mock_db):
        yield mock_db


@pytest.fixture
def mock_mongo_sem_doc():
    mock_db = MagicMock()
    mock_db['sam_resultados'].find_one.return_value = None
    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=mock_db):
        yield mock_db


@pytest.fixture
def mock_mongo_sem_records():
    mock_db = MagicMock()
    mock_db['sam_resultados'].find_one.return_value = {
        **_DOC_BASE,
        'records': [],
    }
    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=mock_db):
        yield mock_db


def test_retorna_status_done_com_doc_valido(
    mock_mongo_com_doc, local_tmp_path
):
    with patch(f'{TASK_MODULE}._output_dir', return_value=local_tmp_path):
        result = task_render_sam.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert result['status'] == 'done'
    assert result['job_id'] == JOB_ID
    assert 'path' in result


def test_salva_arquivo_png(mock_mongo_com_doc, local_tmp_path):
    with patch(f'{TASK_MODULE}._output_dir', return_value=local_tmp_path):
        result = task_render_sam.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    out = Path(result['path'])
    assert out.exists()
    assert out.suffix == '.png'


def test_nome_arquivo_contem_sig_agente(mock_mongo_com_doc, local_tmp_path):
    with patch(f'{TASK_MODULE}._output_dir', return_value=local_tmp_path):
        result = task_render_sam.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert SIG_AGENTE in Path(result['path']).name


def test_nome_arquivo_contem_ano(mock_mongo_com_doc, local_tmp_path):
    with patch(f'{TASK_MODULE}._output_dir', return_value=local_tmp_path):
        result = task_render_sam.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert str(ANO) in Path(result['path']).name


def test_dispara_retry_quando_doc_nao_encontrado(mock_mongo_sem_doc):
    with pytest.raises(Exception, match='retry triggered'):
        task_render_sam.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)


def test_retorna_skipped_quando_records_vazio(
    mock_mongo_sem_records, local_tmp_path
):
    with patch(f'{TASK_MODULE}._output_dir', return_value=local_tmp_path):
        result = task_render_sam.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert result['status'] == 'skipped'
    assert result['reason'] == 'no_records'


def test_busca_por_job_id_e_distribuidora_id(
    mock_mongo_com_doc, local_tmp_path
):
    with patch(f'{TASK_MODULE}._output_dir', return_value=local_tmp_path):
        task_render_sam.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    mock_mongo_com_doc['sam_resultados'].find_one.assert_called_once_with(
        {'job_id': JOB_ID, 'distribuidora_id': DIST_ID},
        {'_id': 0},
    )


def test_plota_todos_os_records(local_tmp_path):
    doc = {
        **_DOC_BASE,
        'records': [
            {'conjunto': f'C{i}', 'sam_km': float(25 - i)} for i in range(25)
        ],
    }
    mock_db = MagicMock()
    mock_db['sam_resultados'].find_one.return_value = doc

    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=mock_db),
        patch(f'{TASK_MODULE}._output_dir', return_value=local_tmp_path),
    ):
        result = task_render_sam.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

    assert result['status'] == 'done'


def test_propaga_excecao_do_mongo():
    with (
        patch(
            f'{TASK_MODULE}.get_mongo_sync_db',
            side_effect=RuntimeError('mongo down'),
        ),
        pytest.raises(RuntimeError, match='mongo down'),
    ):
        task_render_sam.run(JOB_ID, DIST_ID, SIG_AGENTE, ANO)

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.tasks.task_cleanup_files import task_cleanup_files

TASK_MODULE = 'backend.tasks.task_cleanup_files'
JOB_ID = 'cleanup-job-abc'


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    downloads = tmp_path / 'downloads'
    downloads.mkdir()
    tmp_dir = tmp_path / 'tmp'
    tmp_dir.mkdir()
    monkeypatch.setattr(f'{TASK_MODULE}.DOWNLOAD_DIR', downloads)
    monkeypatch.setattr(f'{TASK_MODULE}.TMP_DIR', tmp_dir)
    return downloads, tmp_dir


def _mock_db(render_paths=None):
    job_doc = {'render_paths': render_paths} if render_paths is not None else {}
    db = MagicMock()
    db['jobs'].find_one.return_value = job_doc
    db['jobs'].update_one.return_value = MagicMock()
    return db


def test_remove_zip_e_tmp_dir(dirs):
    downloads, tmp_dir = dirs
    zip_file = downloads / f'{JOB_ID}.zip'
    zip_file.write_bytes(b'PK fake zip')
    job_dir = tmp_dir / JOB_ID
    job_dir.mkdir()
    (job_dir / 'data.gdb').mkdir()

    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=_mock_db()):
        result = task_cleanup_files.run(JOB_ID)

    assert not zip_file.exists()
    assert not job_dir.exists()
    assert str(zip_file) in result['removed']
    assert str(job_dir) in result['removed']
    assert result['errors'] == []


def test_sem_arquivos_retorna_listas_vazias(dirs):
    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=_mock_db()):
        result = task_cleanup_files.run(JOB_ID)

    assert result['removed'] == []
    assert result['errors'] == []


def test_remove_apenas_zip_quando_tmp_ausente(dirs):
    downloads, _ = dirs
    zip_file = downloads / f'{JOB_ID}.zip'
    zip_file.write_bytes(b'PK fake zip')

    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=_mock_db()):
        result = task_cleanup_files.run(JOB_ID)

    assert not zip_file.exists()
    assert len(result['removed']) == 1
    assert result['errors'] == []


def test_remove_apenas_tmp_quando_zip_ausente(dirs):
    _, tmp_dir = dirs
    job_dir = tmp_dir / JOB_ID
    job_dir.mkdir()

    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=_mock_db()):
        result = task_cleanup_files.run(JOB_ID)

    assert not job_dir.exists()
    assert len(result['removed']) == 1
    assert result['errors'] == []


def test_atualiza_mongo_com_status_completed(dirs):
    db = _mock_db()
    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db):
        task_cleanup_files.run(JOB_ID)

    update_call = db['jobs'].update_one.call_args
    _, update_doc = update_call.args
    assert update_doc['$set']['cleanup_status'] == 'completed'
    assert 'cleanup_at' in update_doc['$set']


def test_erro_ao_remover_zip_registrado_em_errors(dirs, monkeypatch):
    downloads, _ = dirs
    zip_file = downloads / f'{JOB_ID}.zip'
    zip_file.write_bytes(b'PK fake zip')

    def _raise(self, *args, **kwargs):
        raise OSError('permission denied')

    monkeypatch.setattr(Path, 'unlink', _raise)

    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=_mock_db()):
        result = task_cleanup_files.run(JOB_ID)

    assert str(zip_file) in result['errors']
    assert result['removed'] == []


def test_mongo_falha_nao_propaga_excecao(dirs):
    downloads, _ = dirs
    zip_file = downloads / f'{JOB_ID}.zip'
    zip_file.write_bytes(b'PK fake zip')

    with patch(f'{TASK_MODULE}.get_mongo_sync_db', side_effect=RuntimeError('mongo down')):
        result = task_cleanup_files.run(JOB_ID)

    assert not zip_file.exists()
    assert result['removed']


def test_remove_imagens_flat_do_render_paths(dirs, tmp_path):
    img = tmp_path / 'grafico_tam.png'
    img.write_bytes(b'\x89PNG')

    render_paths = {'grafico_tam': str(img)}
    db = _mock_db(render_paths=render_paths)

    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db):
        result = task_cleanup_files.run(JOB_ID)

    assert not img.exists()
    assert str(img) in result['removed']


def test_remove_imagens_prophet_aninhadas(dirs, tmp_path):
    dec = tmp_path / 'prophet_ENEL_DEC.png'
    fec = tmp_path / 'prophet_ENEL_FEC.png'
    dec.write_bytes(b'\x89PNG')
    fec.write_bytes(b'\x89PNG')

    render_paths = {
        'prophet': {
            'DEC': str(dec),
            'FEC': str(fec),
        }
    }
    db = _mock_db(render_paths=render_paths)

    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db):
        result = task_cleanup_files.run(JOB_ID)

    assert not dec.exists()
    assert not fec.exists()
    assert str(dec) in result['removed']
    assert str(fec) in result['removed']
    assert result['errors'] == []


def test_remove_render_paths_mistos(dirs, tmp_path):
    img_tam = tmp_path / 'grafico_tam.png'
    img_sam = tmp_path / 'grafico_sam.png'
    dec = tmp_path / 'prophet_ENEL_DEC.png'
    fec = tmp_path / 'prophet_ENEL_FEC.png'
    for f in [img_tam, img_sam, dec, fec]:
        f.write_bytes(b'\x89PNG')

    render_paths = {
        'grafico_tam': str(img_tam),
        'grafico_sam': str(img_sam),
        'prophet': {
            'DEC': str(dec),
            'FEC': str(fec),
        },
    }
    db = _mock_db(render_paths=render_paths)

    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db):
        result = task_cleanup_files.run(JOB_ID)

    for f in [img_tam, img_sam, dec, fec]:
        assert not f.exists()
        assert str(f) in result['removed']
    assert result['errors'] == []


def test_render_paths_prophet_none_nao_quebra(dirs):
    render_paths = {'prophet': None}
    db = _mock_db(render_paths=render_paths)

    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db):
        result = task_cleanup_files.run(JOB_ID)

    assert result['errors'] == []


def test_atualiza_mongo_com_status_failed_quando_imagem_nao_remove(dirs, tmp_path, monkeypatch):
    img = tmp_path / 'grafico_tam.png'
    img.write_bytes(b'\x89PNG')

    render_paths = {'grafico_tam': str(img)}
    db = _mock_db(render_paths=render_paths)

    def _raise(self, *args, **kwargs):
        raise OSError('permission denied')

    monkeypatch.setattr(Path, 'unlink', _raise)

    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db):
        result = task_cleanup_files.run(JOB_ID)

    assert str(img) in result['errors']
    update_call = db['jobs'].update_one.call_args
    _, update_doc = update_call.args
    assert update_doc['$set']['cleanup_status'] == 'failed'
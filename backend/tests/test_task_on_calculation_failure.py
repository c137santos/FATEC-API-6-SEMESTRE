from unittest.mock import MagicMock, patch

from backend.tasks.task_on_calculation_failure import task_on_calculation_failure

TASK_MODULE = 'backend.tasks.task_on_calculation_failure'

_JOB_ID = 'job-fail-1'
_BATCH_ID = 'batch-fail-1'
_DIST_ID = 'dist-fail-1'


def _make_db():
    db = MagicMock()
    return db


# --- sempre acontece ---

def test_sempre_atualiza_job_como_failed():
    db = _make_db()
    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(f'{TASK_MODULE}.task_cleanup_files.apply_async'),
    ):
        task_on_calculation_failure.run(_JOB_ID)

    db['jobs'].update_one.assert_called_once()
    filtro, operacao = db['jobs'].update_one.call_args[0]
    assert filtro == {'job_id': _JOB_ID}
    assert operacao['$set']['report_status'] == 'failed'


def test_sempre_dispara_cleanup_mesmo_sem_batch():
    db = _make_db()
    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(f'{TASK_MODULE}.task_cleanup_files.apply_async') as mock_cleanup,
    ):
        task_on_calculation_failure.run(_JOB_ID, batch_id=None, dist_id=None)

    mock_cleanup.assert_called_once_with(args=[_JOB_ID])


# --- sem batch_id/dist_id ---

def test_sem_batch_id_nao_despacha_proximo():
    db = _make_db()
    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(f'{TASK_MODULE}.task_cleanup_files.apply_async'),
        patch(f'{TASK_MODULE}.task_dispatch_next_in_batch.apply_async') as mock_dispatch,
    ):
        task_on_calculation_failure.run(_JOB_ID, batch_id=None, dist_id=None)

    mock_dispatch.assert_not_called()


# --- com batch_id e dist_id, update bem-sucedido ---

def test_update_ok_despacha_proximo():
    db = _make_db()
    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(f'{TASK_MODULE}.task_cleanup_files.apply_async'),
        patch(f'{TASK_MODULE}._update_batch_dist_status', return_value=True) as mock_update,
        patch(f'{TASK_MODULE}.task_dispatch_next_in_batch.apply_async') as mock_dispatch,
    ):
        task_on_calculation_failure.run(_JOB_ID, batch_id=_BATCH_ID, dist_id=_DIST_ID)

    mock_update.assert_called_once_with(db, _BATCH_ID, _DIST_ID, 'failed')
    mock_dispatch.assert_called_once_with(args=[_BATCH_ID])


# --- com batch_id e dist_id, update no-op (dist já em estado terminal) ---

def test_update_noop_nao_despacha_proximo():
    """Dist já estava 'completed' (task_finalize_batch rodou antes do on_error).
    Não deve despachar o próximo: dispatch já foi feito pela chain ou pelo
    task_dispatch_next_in_batch que falhou e vai se re-agendar sozinho."""
    db = _make_db()
    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(f'{TASK_MODULE}.task_cleanup_files.apply_async'),
        patch(f'{TASK_MODULE}._update_batch_dist_status', return_value=False),
        patch(f'{TASK_MODULE}.task_dispatch_next_in_batch.apply_async') as mock_dispatch,
    ):
        task_on_calculation_failure.run(_JOB_ID, batch_id=_BATCH_ID, dist_id=_DIST_ID)

    mock_dispatch.assert_not_called()


def test_cleanup_chamado_antes_do_dispatch():
    """A limpeza deve preceder o dispatch do próximo item para não acumular
    arquivos de download em disco."""
    call_order = []
    db = _make_db()
    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(f'{TASK_MODULE}.task_cleanup_files.apply_async',
              side_effect=lambda **kw: call_order.append('cleanup')),
        patch(f'{TASK_MODULE}._update_batch_dist_status', return_value=True),
        patch(f'{TASK_MODULE}.task_dispatch_next_in_batch.apply_async',
              side_effect=lambda **kw: call_order.append('dispatch')),
    ):
        task_on_calculation_failure.run(_JOB_ID, batch_id=_BATCH_ID, dist_id=_DIST_ID)

    assert call_order == ['cleanup', 'dispatch']

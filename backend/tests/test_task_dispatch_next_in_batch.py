from unittest.mock import MagicMock, patch

from backend.tasks.task_dispatch_next_in_batch import task_dispatch_next_in_batch

TASK_MODULE = 'backend.tasks.task_dispatch_next_in_batch'
BATCH_MODULE = 'backend.services.pipeline_batch'

_BATCH_ID = 'batch-dispatch-abc'
_DIST_PENDING = {
    'id': 'dist-1', 'nome': 'DIST 1', 'ano': 2026,
    'status': 'pending', 'error': None, 'job_id': None,
}
_BATCH_DOC = {
    'batch_id': _BATCH_ID,
    'user_email': 'test@test.com',
    'distribuidoras': [_DIST_PENDING],
}


def _mock_db(batch_doc=_BATCH_DOC):
    db = MagicMock()
    db.batch_runs.find_one.return_value = batch_doc
    return db


# --- guards ---

def test_sem_batch_id_retorna_skipped():
    result = task_dispatch_next_in_batch.run(None)
    assert result == {'skipped': True}


def test_batch_nao_encontrado_retorna_skipped():
    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=_mock_db(None)):
        result = task_dispatch_next_in_batch.run(_BATCH_ID)
    assert result == {'skipped': True}


def test_sem_pendentes_retorna_done():
    batch_doc = {**_BATCH_DOC, 'distribuidoras': [{**_DIST_PENDING, 'status': 'completed'}]}
    with patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=_mock_db(batch_doc)):
        result = task_dispatch_next_in_batch.run(_BATCH_ID)
    assert result == {'done': True}


# --- happy path ---

def test_despacha_proximo_com_sucesso():
    db = _mock_db()
    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(f'{BATCH_MODULE}._trigger_pipeline_sync') as mock_trigger,
    ):
        result = task_dispatch_next_in_batch.run(_BATCH_ID)

    assert result == {'dispatched': 'dist-1'}
    mock_trigger.assert_called_once()
    assert mock_trigger.call_args[0][0]['id'] == 'dist-1'


def test_despacha_primeiro_pendente_quando_ha_multiplos():
    batch_doc = {
        **_BATCH_DOC,
        'distribuidoras': [
            {**_DIST_PENDING, 'id': 'dist-X', 'status': 'completed'},
            {**_DIST_PENDING, 'id': 'dist-Y', 'status': 'pending'},
            {**_DIST_PENDING, 'id': 'dist-Z', 'status': 'pending'},
        ],
    }
    db = _mock_db(batch_doc)
    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(f'{BATCH_MODULE}._trigger_pipeline_sync') as mock_trigger,
    ):
        result = task_dispatch_next_in_batch.run(_BATCH_ID)

    assert result == {'dispatched': 'dist-Y'}
    assert mock_trigger.call_args[0][0]['id'] == 'dist-Y'


# --- DistribuidoraSemCNPJError ---

def test_cnpj_ausente_marca_skipped_e_despacha_proximo():
    from backend.services.pipeline_batch import DistribuidoraSemCNPJError
    db = _mock_db()
    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(f'{BATCH_MODULE}._trigger_pipeline_sync', side_effect=DistribuidoraSemCNPJError('sem cnpj')),
        patch(f'{BATCH_MODULE}._update_batch_dist_status', return_value=True) as mock_update,
        patch(f'{TASK_MODULE}.task_dispatch_next_in_batch.apply_async') as mock_apply,
    ):
        result = task_dispatch_next_in_batch.run(_BATCH_ID)

    assert result == {'skipped': 'dist-1'}
    mock_update.assert_called_once_with(db, _BATCH_ID, 'dist-1', 'skipped', 'sem cnpj')
    mock_apply.assert_called_once_with(args=[_BATCH_ID])


def test_cnpj_ausente_update_noop_nao_despacha_proximo():
    """Se _update_batch_dist_status retorna False (item já não está pending),
    não deve chamar apply_async para evitar dispatch duplicado."""
    from backend.services.pipeline_batch import DistribuidoraSemCNPJError
    db = _mock_db()
    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(f'{BATCH_MODULE}._trigger_pipeline_sync', side_effect=DistribuidoraSemCNPJError('sem cnpj')),
        patch(f'{BATCH_MODULE}._update_batch_dist_status', return_value=False),
        patch(f'{TASK_MODULE}.task_dispatch_next_in_batch.apply_async') as mock_apply,
    ):
        result = task_dispatch_next_in_batch.run(_BATCH_ID)

    assert result == {'skipped': 'dist-1'}
    mock_apply.assert_not_called()


# --- generic Exception ---

def test_falha_generica_marca_failed_e_despacha_proximo():
    db = _mock_db()
    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(f'{BATCH_MODULE}._trigger_pipeline_sync', side_effect=RuntimeError('erro inesperado')),
        patch(f'{BATCH_MODULE}._update_batch_dist_status', return_value=True) as mock_update,
        patch(f'{TASK_MODULE}.task_dispatch_next_in_batch.apply_async') as mock_apply,
    ):
        result = task_dispatch_next_in_batch.run(_BATCH_ID)

    assert result == {'error': 'dist-1'}
    mock_update.assert_called_once_with(db, _BATCH_ID, 'dist-1', 'failed', 'erro inesperado')
    mock_apply.assert_called_once_with(args=[_BATCH_ID])


def test_falha_generica_update_noop_nao_despacha_proximo():
    """Se _update_batch_dist_status retorna False (item já em estado terminal),
    não deve despachar o próximo — o dispatch já ocorreu por outra via."""
    db = _mock_db()
    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', return_value=db),
        patch(f'{BATCH_MODULE}._trigger_pipeline_sync', side_effect=RuntimeError('erro inesperado')),
        patch(f'{BATCH_MODULE}._update_batch_dist_status', return_value=False),
        patch(f'{TASK_MODULE}.task_dispatch_next_in_batch.apply_async') as mock_apply,
    ):
        result = task_dispatch_next_in_batch.run(_BATCH_ID)

    assert result == {'error': 'dist-1'}
    mock_apply.assert_not_called()


# --- outer exception (falha de infra) ---

def test_erro_infra_nao_propaga_e_reagenda():
    """Exceções de infra (MongoDB/broker fora) não devem propagar para o Celery.
    Se propagassem, o on_error da chain dispararia task_on_calculation_failure
    com o dist_id já 'completed', que não conseguiria atualizar o status nem
    despachar o próximo, travando o batch permanentemente."""
    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', side_effect=ConnectionError('mongo indisponivel')),
        patch(f'{TASK_MODULE}.task_dispatch_next_in_batch.apply_async') as mock_apply,
    ):
        result = task_dispatch_next_in_batch.run(_BATCH_ID)

    assert 'retrying' in result
    mock_apply.assert_called_once_with(args=[_BATCH_ID], countdown=60)


def test_erro_infra_reagendamento_falha_retorna_dict_sem_propagar():
    """Mesmo que o apply_async do reagendamento falhe, a task não deve propagar."""
    with (
        patch(f'{TASK_MODULE}.get_mongo_sync_db', side_effect=ConnectionError('mongo indisponivel')),
        patch(f'{TASK_MODULE}.task_dispatch_next_in_batch.apply_async', side_effect=Exception('broker down')),
    ):
        result = task_dispatch_next_in_batch.run(_BATCH_ID)

    assert 'retrying' in result

from unittest.mock import MagicMock, patch

from backend.tasks.task_trigger_calculations import task_trigger_calculations

TASK_MODULE = 'backend.tasks.task_trigger_calculations'

_JOB_ID = 'job-calc-1'
_DIST_ID = 'dist-1'
_SIG = 'ENEL SP'
_ANO = 2026
_CNPJ = '12.345.678/0001-99'
_BATCH_ID = 'batch-calc-1'

_TASKS_SEM_BATCH = 7   # score + pt_pnt + sam + mapa + tam + finalize + cleanup
_TASKS_COM_BATCH = 8   # + dispatch_next


def _chain_mock():
    obj = MagicMock()
    obj.on_error.return_value = obj
    return obj


# --- chain size ---

def test_sem_batch_id_chain_tem_sete_tasks():
    with patch(f'{TASK_MODULE}.chain') as mock_chain:
        mock_chain.return_value = _chain_mock()
        task_trigger_calculations(_JOB_ID, _DIST_ID, _SIG, _ANO, _CNPJ, batch_id=None)

    assert len(mock_chain.call_args[0]) == _TASKS_SEM_BATCH


def test_com_batch_id_chain_tem_oito_tasks():
    with patch(f'{TASK_MODULE}.chain') as mock_chain:
        mock_chain.return_value = _chain_mock()
        task_trigger_calculations(_JOB_ID, _DIST_ID, _SIG, _ANO, _CNPJ, batch_id=_BATCH_ID)

    assert len(mock_chain.call_args[0]) == _TASKS_COM_BATCH


# --- retorno ---

def test_retorna_job_id():
    with patch(f'{TASK_MODULE}.chain') as mock_chain:
        mock_chain.return_value = _chain_mock()
        result = task_trigger_calculations(_JOB_ID, _DIST_ID, _SIG, _ANO, _CNPJ)

    assert result == {'job_id': _JOB_ID}


# --- on_error e delay ---

def test_on_error_e_delay_chamados():
    with patch(f'{TASK_MODULE}.chain') as mock_chain:
        chain_obj = _chain_mock()
        mock_chain.return_value = chain_obj
        task_trigger_calculations(_JOB_ID, _DIST_ID, _SIG, _ANO, _CNPJ, batch_id=_BATCH_ID)

    chain_obj.on_error.assert_called_once()
    chain_obj.on_error.return_value.delay.assert_called_once()


def test_batch_id_string_vazia_nao_inclui_dispatch_next():
    """String vazia é falsy — não deve incluir dispatch_next na chain."""
    with patch(f'{TASK_MODULE}.chain') as mock_chain:
        mock_chain.return_value = _chain_mock()
        task_trigger_calculations(_JOB_ID, _DIST_ID, _SIG, _ANO, _CNPJ, batch_id='')

    assert len(mock_chain.call_args[0]) == _TASKS_SEM_BATCH

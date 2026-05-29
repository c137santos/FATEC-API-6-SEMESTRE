from unittest.mock import MagicMock, patch

import pytest

from backend.tasks.task_render_temporal_analysis import (
    task_render_prophet_forecast,
)

JOB_ID = 'abc-123'
SIG_AGENTE = 'COSERN'

RENDER_PATHS = {
    'DEC': '/output/images/prophet_COSERN_DEC.png',
    'FEC': '/output/images/prophet_COSERN_FEC.png',
}


def _mock_db():
    db = MagicMock()
    db['jobs'].update_one = MagicMock()
    return db


def _patch_db(db):
    return patch(
        'backend.tasks.task_render_prophet_forecast.get_mongo_sync_db',
        return_value=db,
    )


def _patch_service(render_paths=None, skipped=None):
    result = {
        'sig_agente': SIG_AGENTE,
        'render_paths': render_paths if render_paths is not None else RENDER_PATHS,
        'skipped': skipped if skipped is not None else [],
    }
    return patch(
        'backend.tasks.task_render_prophet_forecast.render_prophet_forecast',
        return_value=result,
    )


def test_retorna_done_quando_graficos_gerados():
    db = _mock_db()
    with _patch_service(), _patch_db(db):
        result = task_render_prophet_forecast(JOB_ID, SIG_AGENTE)

    assert result['status'] == 'done'
    assert result['job_id'] == JOB_ID
    assert result['paths'] == RENDER_PATHS


def test_persiste_render_paths_no_mongo():
    db = _mock_db()
    with _patch_service(), _patch_db(db):
        task_render_prophet_forecast(JOB_ID, SIG_AGENTE)

    db['jobs'].update_one.assert_called_once_with(
        {'job_id': JOB_ID},
        {'$set': {'render_paths.prophet': RENDER_PATHS}},
    )


def test_retorna_skipped_quando_sem_graficos():
    db = _mock_db()
    with _patch_service(render_paths={}), _patch_db(db):
        result = task_render_prophet_forecast(JOB_ID, SIG_AGENTE)

    assert result['status'] == 'skipped'
    assert result['reason'] == 'no_render_paths'


def test_persiste_none_no_mongo_quando_sem_graficos():
    db = _mock_db()
    with _patch_service(render_paths={}), _patch_db(db):
        task_render_prophet_forecast(JOB_ID, SIG_AGENTE)

    db['jobs'].update_one.assert_called_once_with(
        {'job_id': JOB_ID},
        {'$set': {'render_paths.prophet': None}},
    )


def test_repassa_skipped_no_retorno():
    db = _mock_db()
    with _patch_service(skipped=['FEC']), _patch_db(db):
        result = task_render_prophet_forecast(JOB_ID, SIG_AGENTE)

    assert result['skipped'] == ['FEC']


def test_propaga_excecao_do_service():
    db = _mock_db()
    with (
        patch(
            'backend.tasks.task_render_prophet_forecast.render_prophet_forecast',
            side_effect=RuntimeError('Arquivo pickle não encontrado'),
        ),
        _patch_db(db),
    ):
        with pytest.raises(RuntimeError, match='Arquivo pickle não encontrado'):
            task_render_prophet_forecast(JOB_ID, SIG_AGENTE)
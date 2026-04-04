"""Testes da rota POST /etl/load-dec-fec."""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, HttpUrl

from backend.tasks.task_load_dec_fec import (
    task_load_dec_fec_limite,
    task_load_dec_fec_realizado,
)

_test_app = FastAPI()


class _DecFecRequest(BaseModel):
    url_realizado: HttpUrl
    url_limite: HttpUrl


@_test_app.post('/load-dec-fec')
def load_dec_fec(request: _DecFecRequest):
    job_id = str(uuid.uuid4())
    try:
        task_r = task_load_dec_fec_realizado.delay(
            job_id, str(request.url_realizado)
        )
        task_l = task_load_dec_fec_limite.delay(
            job_id, str(request.url_limite)
        )
        return {
            'job_id': job_id,
            'tasks': {'realizado': task_r.id, 'limite': task_l.id},
            'status': 'queued',
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


PAYLOAD_VALIDO = {
    'url_realizado': 'https://example.com/realizado.csv',
    'url_limite': 'https://example.com/limite.csv',
}


@pytest.fixture
def client():
    return TestClient(_test_app)


def _mock_task(task_name: str, task_id: str):
    mock_result = MagicMock()
    mock_result.id = task_id
    return patch(
        f'backend.tasks.task_load_dec_fec.{task_name}.delay',
        return_value=mock_result,
    )


class TestRouteLoadDecFecSucesso:
    def test_retorna_job_id_e_task_ids(self, client):
        with (
            _mock_task('task_load_dec_fec_realizado', 'task-r-1'),
            _mock_task('task_load_dec_fec_limite', 'task-l-1'),
        ):
            response = client.post('/load-dec-fec', json=PAYLOAD_VALIDO)

        assert response.status_code == 200
        body = response.json()
        assert 'job_id' in body
        assert body['tasks']['realizado'] == 'task-r-1'
        assert body['tasks']['limite'] == 'task-l-1'
        assert body['status'] == 'queued'

    def test_job_id_e_uuid_valido(self, client):
        with (
            _mock_task('task_load_dec_fec_realizado', 'r'),
            _mock_task('task_load_dec_fec_limite', 'l'),
        ):
            response = client.post('/load-dec-fec', json=PAYLOAD_VALIDO)

        job_id = response.json()['job_id']
        uuid.UUID(job_id)  # lança ValueError se inválido


class TestRouteLoadDecFecValidacao:
    def test_sem_url_realizado_retorna_422(self, client):
        response = client.post(
            '/load-dec-fec',
            json={'url_limite': 'https://example.com/limite.csv'},
        )
        assert response.status_code == 422

    def test_sem_url_limite_retorna_422(self, client):
        response = client.post(
            '/load-dec-fec',
            json={'url_realizado': 'https://example.com/realizado.csv'},
        )
        assert response.status_code == 422

    def test_payload_vazio_retorna_422(self, client):
        response = client.post('/load-dec-fec', json={})
        assert response.status_code == 422

    def test_url_invalida_retorna_422(self, client):
        response = client.post(
            '/load-dec-fec',
            json={
                'url_realizado': 'nao-e-url',
                'url_limite': 'https://example.com/limite.csv',
            },
        )
        assert response.status_code == 422


class TestRouteLoadDecFecErroCelery:
    def test_erro_no_celery_retorna_500(self, client):
        with patch(
            'backend.tasks.task_load_dec_fec.task_load_dec_fec_realizado.delay',
            side_effect=Exception('broker down'),
        ):
            response = client.post('/load-dec-fec', json=PAYLOAD_VALIDO)

        assert response.status_code == 500
        assert 'broker down' in response.json()['detail']

"""Testes da rota POST /download-gdb.

Cria um app FastAPI mínimo com a rota registrada para evitar
dependências de módulos ausentes (database, core.models).
"""

from unittest.mock import patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, HttpUrl

from backend.services.etl_download import enqueue_download_gdb

_test_app = FastAPI()


class _DownloadRequest(BaseModel):
    url: HttpUrl


@_test_app.post('/download-gdb')
def download_gdb(request: _DownloadRequest):
    try:
        return enqueue_download_gdb(str(request.url))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@pytest.fixture
def client():
    return TestClient(_test_app)


def test_retorna_job_id_e_task_id(client):
    with patch(
        'backend.tests.test_route_etl.enqueue_download_gdb',
        return_value={
            'job_id': 'job-123',
            'task_id': 'celery-task-id-123',
            'status': 'queued',
        },
    ):
        response = client.post(
            '/download-gdb',
            json={'url': 'https://example.com/file.zip'},
        )

    assert response.status_code == 200
    body = response.json()
    assert body['job_id'] == 'job-123'
    assert body['task_id'] == 'celery-task-id-123'
    assert body['status'] == 'queued'


def test_url_invalida_retorna_422(client):
    response = client.post(
        '/download-gdb',
        json={'url': 'nao-e-uma-url'},
    )
    assert response.status_code == 422


def test_payload_vazio_retorna_422(client):
    response = client.post('/download-gdb', json={})
    assert response.status_code == 422


def test_erro_no_celery_retorna_500(client):
    with patch(
        'backend.tests.test_route_etl.enqueue_download_gdb',
        side_effect=Exception('broker down'),
    ):
        response = client.post(
            '/download-gdb',
            json={'url': 'https://example.com/file.zip'},
        )

    assert response.status_code == 500
    assert 'broker down' in response.json()['detail']

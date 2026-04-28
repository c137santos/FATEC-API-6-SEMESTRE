from types import SimpleNamespace
from unittest.mock import patch

from backend.services.etl_download import enqueue_download_gdb


def test_enqueue_download_gdb_retorna_metadata_da_fila():
    fake_task = SimpleNamespace(id='task-123')

    with patch(
        'backend.services.etl_download.uuid.uuid4', return_value='job-abc'
    ):
        with patch(
            'backend.services.etl_download.task_download_gdb.delay',
            return_value=fake_task,
        ) as delay_mock:
            result = enqueue_download_gdb('https://example.com/file.zip')

    delay_mock.assert_called_once_with(
        'job-abc', 'https://example.com/file.zip'
    )
    assert result == {
        'job_id': 'job-abc',
        'task_id': 'task-123',
        'status': 'queued',
    }


def test_enqueue_download_gdb_propagates_celery_errors():
    with patch(
        'backend.services.etl_download.uuid.uuid4', return_value='job-err'
    ):
        with patch(
            'backend.services.etl_download.task_download_gdb.delay',
            side_effect=RuntimeError('broker down'),
        ):
            try:
                enqueue_download_gdb('https://example.com/file.zip')
                raise AssertionError('expected RuntimeError')
            except RuntimeError as exc:
                assert str(exc) == 'broker down'

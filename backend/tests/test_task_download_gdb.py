import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from backend.tasks.task_download_gdb import task_download_gdb


TASK_MODULE = 'backend.tasks.task_download_gdb'


@pytest.fixture(autouse=True)
def _mock_celery_retry():
    with patch.object(
        task_download_gdb,
        'retry',
        side_effect=httpx.HTTPError('retry triggered'),
    ) as mock_retry:
        task_download_gdb.push_request()
        yield mock_retry
        task_download_gdb.pop_request()


@pytest.fixture(autouse=True)
def _mock_next_task_dispatch():
    with patch(f'{TASK_MODULE}.signature') as mock_signature:
        mock_sig_obj = MagicMock()
        mock_signature.return_value = mock_sig_obj
        yield mock_signature


@pytest.fixture
def download_dir(tmp_path, monkeypatch):
    """Redireciona DOWNLOAD_DIR para diretório temporário."""
    d = tmp_path / 'downloads'
    d.mkdir()
    monkeypatch.setattr(f'{TASK_MODULE}.DOWNLOAD_DIR', d)
    return d


def _make_valid_zip(path: Path):
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr('dummy.txt', 'conteudo qualquer')


# ── helpers para fake responses ──


class _FakeStreamOk:
    """Stream que grava ZIP válido."""

    def __init__(self, zip_path):
        self._zip_path = zip_path

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def raise_for_status(self):
        pass

    def iter_bytes(self, chunk_size=8192):
        _make_valid_zip(self._zip_path)
        with open(self._zip_path, 'rb') as f:
            while chunk := f.read(chunk_size):
                yield chunk


class _FakeStreamBadZip:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def raise_for_status(self):
        pass

    def iter_bytes(self, chunk_size=8192):
        yield b'isso nao e um zip'


class _FakeStreamHttpError:
    def __init__(self, status_code=500):
        self._status = status_code

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def raise_for_status(self):
        raise httpx.HTTPStatusError(
            'Server Error',
            request=MagicMock(),
            response=MagicMock(status_code=self._status),
        )

    def iter_bytes(self, chunk_size=8192):
        yield b''


# ═════════════════════════════════════
# Cenários de Sucesso
# ═════════════════════════════════════


def test_retorna_status_downloaded(download_dir):
    zip_path = download_dir / 'abc-123.zip'
    with patch(
        f'{TASK_MODULE}.httpx.stream',
        return_value=_FakeStreamOk(zip_path),
    ):
        result = task_download_gdb.run(
            'abc-123', 'https://example.com/file.zip'
        )

    assert result['job_id'] == 'abc-123'
    assert result['status'] == 'downloaded'
    assert 'abc-123.zip' in result['zip_path']


def test_normaliza_url_arcgis_data_com_barra_final(download_dir):
    zip_path = download_dir / 'arcgis-job.zip'
    with patch(
        f'{TASK_MODULE}.httpx.stream',
        return_value=_FakeStreamOk(zip_path),
    ) as stream_mock:
        task_download_gdb.run(
            'arcgis-job',
            'https://www.arcgis.com/sharing/rest/content/items/abc123/data/',
        )

    called_url = stream_mock.call_args[0][1]
    assert called_url.endswith('/data')


def test_arquivo_zip_valido_no_disco(download_dir):
    zip_path = download_dir / 'job-42.zip'
    with patch(
        f'{TASK_MODULE}.httpx.stream',
        return_value=_FakeStreamOk(zip_path),
    ):
        task_download_gdb.run('job-42', 'https://example.com/file.zip')

    assert zip_path.exists()
    assert zipfile.is_zipfile(zip_path)


# ═════════════════════════════════════
# Validação de entrada
# ═════════════════════════════════════


def test_url_vazia_lanca_runtime_error():
    with pytest.raises(RuntimeError, match='URL de download'):
        task_download_gdb.run('job-1', '')


# ═════════════════════════════════════
# Erros de rede → retry
# ═════════════════════════════════════


def test_http_error_dispara_retry(download_dir, _mock_celery_retry):
    with (
        patch(
            f'{TASK_MODULE}.httpx.stream',
            return_value=_FakeStreamHttpError(500),
        ),
        pytest.raises(httpx.HTTPError),
    ):
        task_download_gdb.run('net-err', 'https://example.com/file.zip')

    _mock_celery_retry.assert_called_once()


def test_timeout_dispara_retry(download_dir, _mock_celery_retry):
    with (
        patch(
            f'{TASK_MODULE}.httpx.stream',
            side_effect=httpx.TimeoutException('timeout'),
        ),
        pytest.raises(httpx.HTTPError),
    ):
        task_download_gdb.run('timeout-job', 'https://example.com/file.zip')

    _mock_celery_retry.assert_called_once()


def test_connect_error_ssl_dispara_retry(download_dir, _mock_celery_retry):
    with (
        patch(
            f'{TASK_MODULE}.httpx.stream',
            side_effect=httpx.ConnectError(
                '[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol'
            ),
        ),
        pytest.raises(httpx.HTTPError),
    ):
        task_download_gdb.run('ssl-eof-job', 'https://example.com/file.zip')

    _mock_celery_retry.assert_called_once()


def test_arquivo_parcial_deletado_apos_erro_http(download_dir):
    # Cria arquivo "parcial" antes do download falhar
    zip_path = download_dir / 'partial-job.zip'
    zip_path.write_bytes(b'lixo parcial')

    with (
        patch(
            f'{TASK_MODULE}.httpx.stream',
            return_value=_FakeStreamHttpError(502),
        ),
        pytest.raises(httpx.HTTPError),
    ):
        task_download_gdb.run('partial-job', 'https://example.com/file.zip')

    assert not zip_path.exists()


# ═════════════════════════════════════
# ZIP inválido
# ═════════════════════════════════════


def test_zip_invalido_lanca_runtime_error(download_dir):
    with (
        patch(
            f'{TASK_MODULE}.httpx.stream',
            return_value=_FakeStreamBadZip(),
        ),
        pytest.raises(RuntimeError, match='ZIP válido'),
    ):
        task_download_gdb.run('bad-zip', 'https://example.com/file.zip')


def test_arquivo_deletado_quando_zip_invalido(download_dir):
    zip_path = download_dir / 'bad-zip.zip'

    with (
        patch(
            f'{TASK_MODULE}.httpx.stream',
            return_value=_FakeStreamBadZip(),
        ),
        pytest.raises(RuntimeError),
    ):
        task_download_gdb.run('bad-zip', 'https://example.com/file.zip')

    assert not zip_path.exists()

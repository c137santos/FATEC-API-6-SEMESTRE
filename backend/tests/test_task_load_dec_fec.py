"""Testes das tasks task_load_dec_fec_realizado e task_load_dec_fec_limite."""
import csv
import io
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from backend.tasks.task_load_dec_fec import (
    _to_date,
    _to_str,
    task_load_dec_fec_limite,
    task_load_dec_fec_realizado,
)

TASK_MODULE = 'backend.tasks.task_load_dec_fec'

URL_REALIZADO = 'https://example.com/realizado.csv'
URL_LIMITE = 'https://example.com/limite.csv'

# ── CSV de exemplo ────────────────────────────────────────────────────────────

COLUNAS_REALIZADO = [
    'DatGeracaoConjuntoDados', 'SigAgente', 'NumCNPJ',
    'IdeConjUndConsumidoras', 'DscConjUndConsumidoras',
    'SigIndicador', 'AnoIndice', 'NumPeriodoIndice', 'VlrIndiceEnviado',
]

COLUNAS_LIMITE = [
    'DatGeracaoConjuntoDados', 'SigAgente', 'NumCNPJ',
    'IdeConjUndConsumidoras', 'DscConjUndConsumidoras',
    'SigIndicador', 'AnoLimiteQualidade', 'VlrLimite',
]


def _csv_bytes(colunas: list[str], linhas: list[list]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=';')
    writer.writerow(colunas)
    writer.writerows(linhas)
    return buf.getvalue().encode('latin-1')


CSV_REALIZADO = _csv_bytes(
    COLUNAS_REALIZADO,
    [
        ['2026-03-05', 'COPEL-DIS', '76535764000143',
         'PR-CRT-001', 'Curitiba Centro', 'DEC', '2023', '1', '5,23'],
        ['2026-03-05', 'COPEL-DIS', '76535764000143',
         'PR-CRT-001', 'Curitiba Centro', 'FEC', '2023', '1', '3,10'],
    ],
)

CSV_LIMITE = _csv_bytes(
    COLUNAS_LIMITE,
    [
        ['2026-03-05', 'COPEL-DIS', '76535764000143',
         'PR-CRT-001', 'Curitiba Centro', 'DEC', '2023', '6,50'],
        ['2026-03-05', 'COPEL-DIS', '76535764000143',
         'PR-CRT-001', 'Curitiba Centro', 'FEC', '2023', '4,00'],
    ],
)

# ── Fake stream HTTP ──────────────────────────────────────────────────────────


class _FakeStream:
    def __init__(self, content: bytes):
        self._content = content
        self.headers = {'content-type': 'text/csv'}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def raise_for_status(self):
        pass

    def iter_bytes(self, chunk_size=8192):
        for i in range(0, len(self._content), chunk_size):
            yield self._content[i: i + chunk_size]


class _FakeStreamHttpError:
    def __init__(self):
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def raise_for_status(self):
        raise httpx.HTTPStatusError(
            'Server Error',
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )

    def iter_bytes(self, chunk_size=8192):
        yield b''


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(f'{TASK_MODULE}.TMP_DIR', tmp_path)
    return tmp_path


@pytest.fixture
def mock_mongo():
    mock_collection = MagicMock()
    mock_collection.bulk_write.return_value = MagicMock(
        upserted_count=2, modified_count=0
    )
    with patch(f'{TASK_MODULE}._get_collection', return_value=mock_collection):
        yield mock_collection


@pytest.fixture(autouse=True)
def _mock_retry_realizado():
    with patch.object(
        task_load_dec_fec_realizado,
        'retry',
        side_effect=httpx.HTTPError('retry triggered'),
    ):
        task_load_dec_fec_realizado.push_request()
        yield
        task_load_dec_fec_realizado.pop_request()


@pytest.fixture(autouse=True)
def _mock_retry_limite():
    with patch.object(
        task_load_dec_fec_limite,
        'retry',
        side_effect=httpx.HTTPError('retry triggered'),
    ):
        task_load_dec_fec_limite.push_request()
        yield
        task_load_dec_fec_limite.pop_request()


# ═════════════════════════════════════════════════════════════════════════════
# task_load_dec_fec_realizado
# ═════════════════════════════════════════════════════════════════════════════


class TestLoadDecFecRealizadoSucesso:
    def test_retorna_status_done(self, tmp_dir, mock_mongo):
        with patch(
            f'{TASK_MODULE}.httpx.stream',
            return_value=_FakeStream(CSV_REALIZADO),
        ):
            result = task_load_dec_fec_realizado.run(
                'job-1', URL_REALIZADO
            )

        assert result['status'] == 'done'
        assert result['job_id'] == 'job-1'

    def test_chama_bulk_write_com_documentos(self, tmp_dir, mock_mongo):
        with patch(
            f'{TASK_MODULE}.httpx.stream',
            return_value=_FakeStream(CSV_REALIZADO),
        ):
            task_load_dec_fec_realizado.run('job-2', URL_REALIZADO)

        mock_mongo.bulk_write.assert_called_once()
        ops = mock_mongo.bulk_write.call_args[0][0]
        assert len(ops) == 2

    def test_documento_tem_campos_corretos(self, tmp_dir, mock_mongo):
        with patch(
            f'{TASK_MODULE}.httpx.stream',
            return_value=_FakeStream(CSV_REALIZADO),
        ):
            task_load_dec_fec_realizado.run('job-3', URL_REALIZADO)

        op = mock_mongo.bulk_write.call_args[0][0][0]
        doc = op._doc['$set']
        assert doc['dat_geracao'] == datetime(2026, 3, 5)
        assert doc['sig_agente'] == 'COPEL-DIS'
        assert doc['sig_indicador'] == 'DEC'
        assert doc['ano_indice'] == 2023
        assert doc['num_periodo'] == 1
        assert doc['vlr_indice'] == pytest.approx(5.23)

    def test_arquivo_temporario_removido_apos_sucesso(self, tmp_dir, mock_mongo):
        with patch(
            f'{TASK_MODULE}.httpx.stream',
            return_value=_FakeStream(CSV_REALIZADO),
        ):
            task_load_dec_fec_realizado.run('job-4', URL_REALIZADO)

        assert not (tmp_dir / 'job-4_realizado.csv').exists()


class TestHelpers:
    def test_to_str_strip_espacos(self):
        assert _to_str('COPEL-DIS   ') == 'COPEL-DIS'

    def test_to_str_vazio_retorna_none(self):
        assert _to_str('') is None
        assert _to_str('   ') is None

    def test_to_date_converte_iso(self):
        assert _to_date('2026-03-05') == datetime(2026, 3, 5)

    def test_to_date_vazio_retorna_none(self):
        assert _to_date('') is None


class TestLoadDecFecRealizadoCaracteresEspeciais:
    def test_caracteres_latin1_sao_decodificados(self, tmp_dir, mock_mongo):
        csv_latin1 = _csv_bytes(COLUNAS_REALIZADO, [
            ['2026-03-05', 'COPEL-DIS', '76535764000143',
             'PR-CRT-001', 'Curitibá Centro', 'DEC', '2023', '1', '5,23'],
        ])
        with patch(
            f'{TASK_MODULE}.httpx.stream',
            return_value=_FakeStream(csv_latin1),
        ):
            result = task_load_dec_fec_realizado.run('job-latin1', URL_REALIZADO)

        assert result['status'] == 'done'

    def test_valor_numerico_vazio_vira_none(self, tmp_dir, mock_mongo):
        csv_vazio = _csv_bytes(COLUNAS_REALIZADO, [
            ['2026-03-05', 'COPEL-DIS', '76535764000143',
             'PR-CRT-001', 'Curitiba Centro', 'DEC', '2023', '1', ''],
        ])
        with patch(
            f'{TASK_MODULE}.httpx.stream',
            return_value=_FakeStream(csv_vazio),
        ):
            result = task_load_dec_fec_realizado.run('job-empty', URL_REALIZADO)

        assert result['status'] == 'done'
        op = mock_mongo.bulk_write.call_args[0][0][0]
        assert op._doc['$set']['vlr_indice'] is None


class TestLoadDecFecRealizadoErroRede:
    def test_http_error_dispara_retry(self, tmp_dir, mock_mongo):
        with (
            patch(
                f'{TASK_MODULE}.httpx.stream',
                return_value=_FakeStreamHttpError(),
            ),
            pytest.raises(httpx.HTTPError),
        ):
            task_load_dec_fec_realizado.run('job-err', URL_REALIZADO)

    def test_timeout_dispara_retry(self, tmp_dir, mock_mongo):
        with (
            patch(
                f'{TASK_MODULE}.httpx.stream',
                side_effect=httpx.TimeoutException('timeout'),
            ),
            pytest.raises(httpx.HTTPError),
        ):
            task_load_dec_fec_realizado.run('job-timeout', URL_REALIZADO)

    def test_arquivo_temporario_removido_apos_erro(self, tmp_dir, mock_mongo):
        with (
            patch(
                f'{TASK_MODULE}.httpx.stream',
                return_value=_FakeStreamHttpError(),
            ),
            pytest.raises(httpx.HTTPError),
        ):
            task_load_dec_fec_realizado.run('job-clean', URL_REALIZADO)

        assert not (tmp_dir / 'job-clean_realizado.csv').exists()


# ═════════════════════════════════════════════════════════════════════════════
# task_load_dec_fec_limite
# ═════════════════════════════════════════════════════════════════════════════


class TestLoadDecFecLimiteSucesso:
    def test_retorna_status_done(self, tmp_dir, mock_mongo):
        with patch(
            f'{TASK_MODULE}.httpx.stream',
            return_value=_FakeStream(CSV_LIMITE),
        ):
            result = task_load_dec_fec_limite.run('job-lim-1', URL_LIMITE)

        assert result['status'] == 'done'
        assert result['job_id'] == 'job-lim-1'

    def test_chama_bulk_write_com_documentos(self, tmp_dir, mock_mongo):
        with patch(
            f'{TASK_MODULE}.httpx.stream',
            return_value=_FakeStream(CSV_LIMITE),
        ):
            task_load_dec_fec_limite.run('job-lim-2', URL_LIMITE)

        mock_mongo.bulk_write.assert_called_once()
        ops = mock_mongo.bulk_write.call_args[0][0]
        assert len(ops) == 2

    def test_documento_tem_campos_corretos(self, tmp_dir, mock_mongo):
        with patch(
            f'{TASK_MODULE}.httpx.stream',
            return_value=_FakeStream(CSV_LIMITE),
        ):
            task_load_dec_fec_limite.run('job-lim-3', URL_LIMITE)

        op = mock_mongo.bulk_write.call_args[0][0][0]
        doc = op._doc['$set']
        assert doc['dat_geracao'] == datetime(2026, 3, 5)
        assert doc['sig_agente'] == 'COPEL-DIS'
        assert doc['sig_indicador'] == 'DEC'
        assert doc['ano_limite'] == 2023
        assert doc['vlr_limite'] == pytest.approx(6.50)

    def test_arquivo_temporario_removido_apos_sucesso(self, tmp_dir, mock_mongo):
        with patch(
            f'{TASK_MODULE}.httpx.stream',
            return_value=_FakeStream(CSV_LIMITE),
        ):
            task_load_dec_fec_limite.run('job-lim-4', URL_LIMITE)

        assert not (tmp_dir / 'job-lim-4_limite.csv').exists()


class TestLoadDecFecLimiteErroRede:
    def test_http_error_dispara_retry(self, tmp_dir, mock_mongo):
        with (
            patch(
                f'{TASK_MODULE}.httpx.stream',
                return_value=_FakeStreamHttpError(),
            ),
            pytest.raises(httpx.HTTPError),
        ):
            task_load_dec_fec_limite.run('lim-err', URL_LIMITE)

    def test_timeout_dispara_retry(self, tmp_dir, mock_mongo):
        with (
            patch(
                f'{TASK_MODULE}.httpx.stream',
                side_effect=httpx.TimeoutException('timeout'),
            ),
            pytest.raises(httpx.HTTPError),
        ):
            task_load_dec_fec_limite.run('lim-timeout', URL_LIMITE)

    def test_arquivo_temporario_removido_apos_erro(self, tmp_dir, mock_mongo):
        with (
            patch(
                f'{TASK_MODULE}.httpx.stream',
                return_value=_FakeStreamHttpError(),
            ),
            pytest.raises(httpx.HTTPError),
        ):
            task_load_dec_fec_limite.run('lim-clean', URL_LIMITE)

        assert not (tmp_dir / 'lim-clean_limite.csv').exists()

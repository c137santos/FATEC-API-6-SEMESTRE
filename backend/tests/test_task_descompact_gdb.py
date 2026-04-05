import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.tasks.task_descompact_gdb import (
    REQUIRED_SCHEMA,
    task_descompact_gdb,
)

TASK_MODULE = 'backend.tasks.task_descompact_gdb'


@pytest.fixture(autouse=True)
def _push_request():
    task_descompact_gdb.push_request()
    yield
    task_descompact_gdb.pop_request()


@pytest.fixture
def tmp_dir(tmp_path, monkeypatch):
    """Redireciona TMP_DIR para diretório temporário."""
    d = tmp_path / 'tmp'
    d.mkdir()
    monkeypatch.setattr(f'{TASK_MODULE}.TMP_DIR', d)
    return d


@pytest.fixture
def valid_zip(tmp_path):
    """ZIP com diretório .gdb dentro."""
    zip_path = tmp_path / 'arquivo.zip'
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr('dados.gdb/a00000001.gdbtable', 'fake gdb content')
    return zip_path


@pytest.fixture
def no_gdb_zip(tmp_path):
    """ZIP sem nenhum .gdb."""
    zip_path = tmp_path / 'nogdb.zip'
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr('README.txt', 'no gdb here')
    return zip_path


# ── helpers de mock fiona ────────────────────────────────────────────────────


class _FakeDataset:
    def __init__(self, columns: set[str], rows: list[dict] | None = None):
        self.schema = {'properties': {col: 'str' for col in columns}}
        self._rows = rows or []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __iter__(self):
        return iter(self._rows)

    def __len__(self):
        return len(self._rows)


def _fiona_open_ok(missing_cols: dict[str, set[str]] | None = None):
    """side_effect para fiona.open com todas as colunas (ou removendo algumas)."""

    def open_fn(path, layer=None):
        cols = set(REQUIRED_SCHEMA.get(layer, set()))
        if missing_cols and layer in missing_cols:
            cols -= missing_cols[layer]
        return _FakeDataset(cols)

    return open_fn


def _fiona_layers(missing_layer: str | None = None) -> list[str]:
    layers = list(REQUIRED_SCHEMA.keys())
    if missing_layer:
        layers = [la for la in layers if la != missing_layer]
    return layers


# ═════════════════════════════════════
# Sucesso
# ═════════════════════════════════════


class TestDescompactGdbSuccess:
    def test_retorna_status_extracted(self, tmp_dir, valid_zip):
        with (
            patch(
                f'{TASK_MODULE}.fiona.listlayers', return_value=_fiona_layers()
            ),
            patch(f'{TASK_MODULE}.fiona.open', side_effect=_fiona_open_ok()),
            patch(f'{TASK_MODULE}.chord') as mock_chord,
        ):
            mock_chord.return_value.delay = MagicMock()
            result = task_descompact_gdb.run('job-1', str(valid_zip))

        assert result['job_id'] == 'job-1'
        assert result['status'] == 'extracted'

    def test_gdb_path_no_retorno_e_string(self, tmp_dir, valid_zip):
        with (
            patch(
                f'{TASK_MODULE}.fiona.listlayers', return_value=_fiona_layers()
            ),
            patch(f'{TASK_MODULE}.fiona.open', side_effect=_fiona_open_ok()),
            patch(f'{TASK_MODULE}.chord') as mock_chord,
        ):
            mock_chord.return_value.delay = MagicMock()
            result = task_descompact_gdb.run('job-1', str(valid_zip))

        assert isinstance(result['gdb_path'], str)
        assert result['gdb_path'].endswith('.gdb')

    def test_gdb_extraido_no_diretorio_tmp(self, tmp_dir, valid_zip):
        with (
            patch(
                f'{TASK_MODULE}.fiona.listlayers', return_value=_fiona_layers()
            ),
            patch(f'{TASK_MODULE}.fiona.open', side_effect=_fiona_open_ok()),
            patch(f'{TASK_MODULE}.chord') as mock_chord,
        ):
            mock_chord.return_value.delay = MagicMock()
            result = task_descompact_gdb.run('job-1', str(valid_zip))

        assert str(tmp_dir / 'job-1') in result['gdb_path']

    def test_chord_disparado_uma_vez(self, tmp_dir, valid_zip):
        with (
            patch(
                f'{TASK_MODULE}.fiona.listlayers', return_value=_fiona_layers()
            ),
            patch(f'{TASK_MODULE}.fiona.open', side_effect=_fiona_open_ok()),
            patch(f'{TASK_MODULE}.chord') as mock_chord,
        ):
            mock_chord_instance = MagicMock()
            mock_chord.return_value = mock_chord_instance
            task_descompact_gdb.run('job-1', str(valid_zip))

        mock_chord.assert_called_once()
        mock_chord_instance.delay.assert_called_once()

    def test_chord_header_tem_tres_tasks(self, tmp_dir, valid_zip):
        with (
            patch(
                f'{TASK_MODULE}.fiona.listlayers', return_value=_fiona_layers()
            ),
            patch(f'{TASK_MODULE}.fiona.open', side_effect=_fiona_open_ok()),
            patch(f'{TASK_MODULE}.chord') as mock_chord,
        ):
            mock_chord.return_value.delay = MagicMock()
            task_descompact_gdb.run('job-1', str(valid_zip))

        header, _callback = mock_chord.call_args.args
        assert len(header) == 3

    def test_gdb_path_passado_como_string_para_cada_task(
        self, tmp_dir, valid_zip
    ):
        with (
            patch(
                f'{TASK_MODULE}.fiona.listlayers', return_value=_fiona_layers()
            ),
            patch(f'{TASK_MODULE}.fiona.open', side_effect=_fiona_open_ok()),
            patch(f'{TASK_MODULE}.chord') as mock_chord,
            patch(f'{TASK_MODULE}.signature') as mock_sig,
        ):
            mock_chord.return_value.delay = MagicMock()
            result = task_descompact_gdb.run('job-1', str(valid_zip))

        gdb_path = result['gdb_path']
        # As três tasks de processamento recebem gdb_path (str) como argumento
        calls_with_gdb = [
            c
            for c in mock_sig.call_args_list
            if c.kwargs.get('args') and gdb_path in c.kwargs['args']
        ]
        assert len(calls_with_gdb) == 3

    def test_usa_tasks_chunk_de_ssdmt_quando_habilitado(
        self, tmp_dir, valid_zip, monkeypatch
    ):
        monkeypatch.setattr(
            f'{TASK_MODULE}.SSDMT_PARALLEL_CHUNK_SIZE',
            2,
        )

        def open_fn(path, layer=None):
            cols = set(REQUIRED_SCHEMA.get(layer, set()))
            if layer == 'SSDMT':
                rows = [
                    {'properties': {'COD_ID': f'SS-{i}'}} for i in range(5)
                ]
                return _FakeDataset(cols, rows=rows)
            return _FakeDataset(cols)

        with (
            patch(
                f'{TASK_MODULE}.fiona.listlayers', return_value=_fiona_layers()
            ),
            patch(f'{TASK_MODULE}.fiona.open', side_effect=open_fn),
            patch(f'{TASK_MODULE}.chord') as mock_chord,
            patch(f'{TASK_MODULE}.signature') as mock_sig,
        ):
            mock_chord.return_value.delay = MagicMock()
            task_descompact_gdb.run('job-1', str(valid_zip))

        chunk_calls = [
            c
            for c in mock_sig.call_args_list
            if c.args and c.args[0] == 'etl.processar_ssdmt_chunk'
        ]
        assert len(chunk_calls) == 3


# ═════════════════════════════════════
# Quebra: sem .gdb no ZIP
# ═════════════════════════════════════


class TestDescompactGdbSemGdb:
    def test_sem_gdb_lanca_runtime_error(self, tmp_dir, no_gdb_zip):
        with pytest.raises(RuntimeError, match=r'\.gdb'):
            task_descompact_gdb.run('job-2', str(no_gdb_zip))


# ═════════════════════════════════════
# Quebra: camada ausente
# ═════════════════════════════════════


class TestDescompactGdbCamadaAusente:
    @pytest.mark.parametrize('missing_layer', list(REQUIRED_SCHEMA.keys()))
    def test_camada_ausente_lanca_runtime_error(
        self, tmp_dir, valid_zip, missing_layer
    ):
        with (
            patch(
                f'{TASK_MODULE}.fiona.listlayers',
                return_value=_fiona_layers(missing_layer=missing_layer),
            ),
            patch(f'{TASK_MODULE}.fiona.open', side_effect=_fiona_open_ok()),
            pytest.raises(RuntimeError, match=missing_layer),
        ):
            task_descompact_gdb.run('job-3', str(valid_zip))


# ═════════════════════════════════════
# Quebra: coluna obrigatória faltando
# ═════════════════════════════════════


class TestDescompactGdbColunaFaltando:
    @pytest.mark.parametrize('layer', list(REQUIRED_SCHEMA.keys()))
    def test_coluna_faltando_lanca_runtime_error(
        self, tmp_dir, valid_zip, layer
    ):
        one_col = next(iter(REQUIRED_SCHEMA[layer]))
        with (
            patch(
                f'{TASK_MODULE}.fiona.listlayers',
                return_value=_fiona_layers(),
            ),
            patch(
                f'{TASK_MODULE}.fiona.open',
                side_effect=_fiona_open_ok(missing_cols={layer: {one_col}}),
            ),
            pytest.raises(RuntimeError, match=layer),
        ):
            task_descompact_gdb.run('job-4', str(valid_zip))

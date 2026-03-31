from unittest.mock import patch

import pytest

from backend.tasks.task_process_layers import (
    REQUIRED_CONJ_COLUMNS,
    task_processar_conj,
)


TASK_MODULE = 'backend.tasks.task_process_layers'


class _FakeDataset:
    def __init__(self, columns: set[str], rows: list[dict]):
        self.schema = {'properties': {col: 'str' for col in columns}}
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __iter__(self):
        return iter(self._rows)


def _feature(cod_id, nome, dist):
    return {'properties': {'COD_ID': cod_id, 'NOME': nome, 'DIST': dist}}


def test_retorna_records_com_colunas_necessarias():
    dataset = _FakeDataset(
        columns=set(REQUIRED_CONJ_COLUMNS),
        rows=[
            _feature(1, ' Centro ', 404),
            _feature(2, 'Norte', 404),
        ],
    )

    with patch(f'{TASK_MODULE}.fiona.open', return_value=dataset):
        result = task_processar_conj.run('job-1', '/tmp/arquivo.gdb')

    assert result['layer'] == 'CONJ'
    assert result['job_id'] == 'job-1'
    assert result['total'] == 2
    assert result['descartados'] == 0
    assert len(result['records']) == 2

    record = result['records'][0]
    assert record['cod_id'] == 1
    assert record['nome'] == 'Centro'
    assert record['dist'] == 404
    assert record['job_id'] == 'job-1'
    assert 'processed_at' in record

def test_descarta_registro_sem_cod_id():
    dataset = _FakeDataset(
        columns=set(REQUIRED_CONJ_COLUMNS),
        rows=[
            _feature(None, 'Sem id', 404),
            _feature(3, 'Sul', 404),
        ],
    )

    with patch(f'{TASK_MODULE}.fiona.open', return_value=dataset):
        result = task_processar_conj.run('job-2', '/tmp/arquivo.gdb')

    assert result['total'] == 1
    assert result['descartados'] == 1
    assert result['records'][0]['cod_id'] == 3

def test_lanca_erro_quando_faltam_colunas():
    dataset = _FakeDataset(columns={'COD_ID', 'NOME'}, rows=[_feature(1, 'A', 1)])

    with patch(f'{TASK_MODULE}.fiona.open', return_value=dataset):
        with pytest.raises(RuntimeError, match='Camada CONJ sem colunas'):
            task_processar_conj.run('job-3', '/tmp/arquivo.gdb')

def test_lanca_erro_sem_registros_validos():
    dataset = _FakeDataset(
        columns=set(REQUIRED_CONJ_COLUMNS),
        rows=[_feature(None, 'A', 404)],
    )

    with patch(f'{TASK_MODULE}.fiona.open', return_value=dataset):
        with pytest.raises(
            RuntimeError,
            match='Camada CONJ sem registros validos apos limpeza',
        ):
            task_processar_conj.run('job-4', '/tmp/arquivo.gdb')

from unittest.mock import patch

import pytest

from backend.tasks.task_process_layers import (
    REQUIRED_CTMT_COLUMNS,
    REQUIRED_CONJ_COLUMNS,
    task_processar_ctmt,
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


def _feature_ctmt(
    cod_id,
    nome=' Circuito ',
    dist='404',
    ene_01=100,
    perd_a3a=1.1,
):
    return {
        'properties': {
            'COD_ID': cod_id,
            'NOME': nome,
            'DIST': dist,
            'ENE_01': ene_01,
            'ENE_02': 101,
            'ENE_03': 102,
            'ENE_04': 103,
            'ENE_05': 104,
            'ENE_06': 105,
            'ENE_07': 106,
            'ENE_08': 107,
            'ENE_09': 108,
            'ENE_10': 109,
            'ENE_11': 110,
            'ENE_12': 111,
            'PERD_A3a': perd_a3a,
            'PERD_A4': 2.2,
            'PERD_B': 3.3,
            'PERD_MED': 4.4,
            'PERD_A3aA4': 5.5,
            'PERD_A3a_B': 6.6,
            'PERD_A4A3a': 7.7,
            'PERD_A4_B': 8.8,
            'PERD_B_A3a': 9.9,
            'PERD_B_A4': 10.1,
        }
    }


def test_ctmt_retorna_records_com_colunas_necessarias():
    dataset = _FakeDataset(
        columns=set(REQUIRED_CTMT_COLUMNS),
        rows=[
            _feature_ctmt(' CT-01 ', nome=' Centro '),
            _feature_ctmt('CT-02', nome='Norte', ene_01=200, perd_a3a=11.1),
        ],
    )

    with patch(f'{TASK_MODULE}.fiona.open', return_value=dataset):
        result = task_processar_ctmt.run('job-ctmt-1', '/tmp/arquivo.gdb')

    assert result['layer'] == 'CTMT'
    assert result['job_id'] == 'job-ctmt-1'
    assert result['total'] == 2
    assert result['descartados'] == 0

    record = result['records'][0]
    assert record['cod_id'] == 'CT-01'
    assert record['nome'] == 'Centro'
    assert record['dist'] == '404'
    assert record['ene_01'] == 100
    assert record['perd_a3a'] == 1.1
    assert 'processed_at' in record


def test_ctmt_descarta_registro_sem_cod_id():
    dataset = _FakeDataset(
        columns=set(REQUIRED_CTMT_COLUMNS),
        rows=[
            _feature_ctmt(None),
            _feature_ctmt('   '),
            _feature_ctmt('CT-VALIDO', nome=' Sul '),
        ],
    )

    with patch(f'{TASK_MODULE}.fiona.open', return_value=dataset):
        result = task_processar_ctmt.run('job-ctmt-2', '/tmp/arquivo.gdb')

    assert result['total'] == 1
    assert result['descartados'] == 2
    assert result['records'][0]['cod_id'] == 'CT-VALIDO'
    assert result['records'][0]['nome'] == 'Sul'


def test_ctmt_lanca_erro_quando_faltam_colunas():
    dataset = _FakeDataset(
        columns={'COD_ID', 'NOME', 'DIST'},
        rows=[_feature_ctmt('CT-01')],
    )

    with patch(f'{TASK_MODULE}.fiona.open', return_value=dataset):
        with pytest.raises(RuntimeError, match='Camada CTMT sem colunas'):
            task_processar_ctmt.run('job-ctmt-3', '/tmp/arquivo.gdb')


def test_ctmt_lanca_erro_sem_registros_validos():
    dataset = _FakeDataset(
        columns=set(REQUIRED_CTMT_COLUMNS),
        rows=[_feature_ctmt(None), _feature_ctmt('   ')],
    )

    with patch(f'{TASK_MODULE}.fiona.open', return_value=dataset):
        with pytest.raises(
            RuntimeError,
            match='Camada CTMT sem registros validos apos limpeza',
        ):
            task_processar_ctmt.run('job-ctmt-4', '/tmp/arquivo.gdb')


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
    dataset = _FakeDataset(
        columns={'COD_ID', 'NOME'}, rows=[_feature(1, 'A', 1)]
    )

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

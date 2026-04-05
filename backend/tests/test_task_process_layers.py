import json
from unittest.mock import patch

import pytest

from backend.tasks.task_process_layers import (
    REQUIRED_CTMT_COLUMNS,
    REQUIRED_CONJ_COLUMNS,
    REQUIRED_SSDMT_COLUMNS,
    SSDMT_BATCH_SIZE,
    task_processar_ctmt,
    task_processar_conj,
    task_processar_ssdmt_chunk,
    task_processar_ssdmt,
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


class _FakeIterDataset:
    def __init__(self, columns: set[str], rows: list[dict], crs=None, crs_wkt=None):
        self.schema = {'properties': {col: 'str' for col in columns}}
        self._rows = rows
        self._cursor = 0
        self.crs = crs if crs is not None else {'init': 'epsg:3857'}
        self.crs_wkt = crs_wkt

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __iter__(self):
        return self

    def __next__(self):
        if self._cursor >= len(self._rows):
            raise StopIteration
        row = self._rows[self._cursor]
        self._cursor += 1
        return row


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


def _feature_ssdmt(cod_id, ctmt, geometry=None, conj='CJ', comp=10, dist='404'):
    if geometry is None:
        geometry = {'type': 'Point', 'coordinates': [0.0, 0.0]}

    return {
        'properties': {
            'COD_ID': cod_id,
            'CTMT': ctmt,
            'CONJ': conj,
            'COMP': comp,
            'DIST': dist,
        },
        'geometry': geometry,
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


def test_ssdmt_retorna_referencia_tabular_e_geo_em_batches(tmp_path):
    rows = []
    for i in range(SSDMT_BATCH_SIZE + 2):
        rows.append(_feature_ssdmt(f'SS-{i}', f'CT-{i}'))

    dataset = _FakeIterDataset(
        columns=set(REQUIRED_SSDMT_COLUMNS),
        rows=rows,
        crs={'init': 'epsg:3857'},
    )

    class _FakeTransformer:
        def transform(self, x, y, z=None):
            return (x + 1.0, y + 1.0)

    with (
        patch(f'{TASK_MODULE}.fiona.open', return_value=dataset),
        patch(f'{TASK_MODULE}.pyproj.CRS.from_user_input', return_value='EPSG:3857'),
        patch(
            f'{TASK_MODULE}.pyproj.Transformer.from_crs',
            return_value=_FakeTransformer(),
        ),
    ):
        result = task_processar_ssdmt.run(
            'job-ssdmt-1', str(tmp_path / 'arquivo.gdb')
        )

    assert result['layer'] == 'SSDMT'
    assert result['job_id'] == 'job-ssdmt-1'
    assert result['descartados'] == 0
    assert result['total'] == SSDMT_BATCH_SIZE + 2

    assert result['ssdmt_tabular']['storage_type'] == 'ndjson'
    assert result['ssdmt_tabular']['records_count'] == SSDMT_BATCH_SIZE + 2
    tabular_path = result['ssdmt_tabular']['path']
    with open(tabular_path, encoding='utf-8') as tabular_file:
        first_tabular_line = tabular_file.readline().strip()
    first_tabular = json.loads(first_tabular_line)
    assert first_tabular['cod_id'] == 'SS-0'
    assert first_tabular['ctmt'] == 'CT-0'

    assert result['ssdmt_geo']['storage_type'] == 'ndjson'
    assert result['ssdmt_geo']['records_count'] == SSDMT_BATCH_SIZE + 2
    assert result['ssdmt_geo']['crs'] == 'EPSG:4326'

    geo_path = result['ssdmt_geo']['path']
    with open(geo_path, encoding='utf-8') as geo_file:
        first_line = geo_file.readline().strip()
    assert json.loads(first_line)['type'] == 'Feature'


def test_ssdmt_descarta_cod_id_ou_ctmt_nulos(tmp_path):
    rows = [
        _feature_ssdmt(None, 'CT-1'),
        _feature_ssdmt('   ', 'CT-2'),
        _feature_ssdmt('SS-1', None),
        _feature_ssdmt('SS-2', '  '),
        _feature_ssdmt('SS-OK', 'CT-OK'),
    ]
    dataset = _FakeIterDataset(
        columns=set(REQUIRED_SSDMT_COLUMNS),
        rows=rows,
        crs={'init': 'epsg:3857'},
    )

    class _FakeTransformer:
        def transform(self, x, y, z=None):
            return (x, y)

    with (
        patch(f'{TASK_MODULE}.fiona.open', return_value=dataset),
        patch(f'{TASK_MODULE}.pyproj.CRS.from_user_input', return_value='EPSG:3857'),
        patch(
            f'{TASK_MODULE}.pyproj.Transformer.from_crs',
            return_value=_FakeTransformer(),
        ),
    ):
        result = task_processar_ssdmt.run(
            'job-ssdmt-2', str(tmp_path / 'arquivo.gdb')
        )

    assert result['total'] == 1
    assert result['descartados'] == 4
    tabular_path = result['ssdmt_tabular']['path']
    with open(tabular_path, encoding='utf-8') as tabular_file:
        first_tabular_line = tabular_file.readline().strip()
    assert json.loads(first_tabular_line)['cod_id'] == 'SS-OK'
    assert result['ssdmt_geo']['records_count'] == 1


def test_ssdmt_lanca_erro_sem_crs_identificavel(tmp_path):
    dataset = _FakeIterDataset(
        columns=set(REQUIRED_SSDMT_COLUMNS),
        rows=[_feature_ssdmt('SS-1', 'CT-1')],
        crs=None,
        crs_wkt=None,
    )
    dataset.crs = None

    with (
        patch(f'{TASK_MODULE}.fiona.open', return_value=dataset),
        patch(
            f'{TASK_MODULE}.pyproj.CRS.from_user_input',
            side_effect=Exception('crs invalido'),
        ),
    ):
        with pytest.raises(
            RuntimeError,
            match='Camada SSDMT sem CRS identificavel no arquivo',
        ):
            task_processar_ssdmt.run(
                'job-ssdmt-3', str(tmp_path / 'arquivo.gdb')
            )


def test_ssdmt_lanca_erro_com_falha_reprojecao_acima_de_1_por_cento(tmp_path):
    rows = [_feature_ssdmt(f'SS-{i}', f'CT-{i}') for i in range(100)]
    dataset = _FakeIterDataset(
        columns=set(REQUIRED_SSDMT_COLUMNS),
        rows=rows,
        crs={'init': 'epsg:3857'},
    )

    class _FakeTransformer:
        def transform(self, x, y, z=None):
            return (x, y)

    with (
        patch(f'{TASK_MODULE}.fiona.open', return_value=dataset),
        patch(f'{TASK_MODULE}.pyproj.CRS.from_user_input', return_value='EPSG:3857'),
        patch(
            f'{TASK_MODULE}.pyproj.Transformer.from_crs',
            return_value=_FakeTransformer(),
        ),
        patch(
            f'{TASK_MODULE}.shape',
            side_effect=[Exception('falha reprojecao')] * 2
            + [
                {
                    'type': 'Point',
                    'coordinates': [0.0, 0.0],
                }
            ]
            * 98,
        ),
        patch(
            f'{TASK_MODULE}.transform',
            side_effect=lambda func, geom: geom,
        ),
        patch(
            f'{TASK_MODULE}.mapping',
            side_effect=lambda geom: geom,
        ),
    ):
        with pytest.raises(
            RuntimeError,
            match='Camada SSDMT com falha de reprojecao acima do limite',
        ):
            task_processar_ssdmt.run(
                'job-ssdmt-4', str(tmp_path / 'arquivo.gdb')
            )


def test_ssdmt_lanca_erro_sem_registros_validos(tmp_path):
    rows = [_feature_ssdmt(None, None), _feature_ssdmt('  ', '  ')]
    dataset = _FakeIterDataset(
        columns=set(REQUIRED_SSDMT_COLUMNS),
        rows=rows,
        crs={'init': 'epsg:3857'},
    )

    class _FakeTransformer:
        def transform(self, x, y, z=None):
            return (x, y)

    with (
        patch(f'{TASK_MODULE}.fiona.open', return_value=dataset),
        patch(f'{TASK_MODULE}.pyproj.CRS.from_user_input', return_value='EPSG:3857'),
        patch(
            f'{TASK_MODULE}.pyproj.Transformer.from_crs',
            return_value=_FakeTransformer(),
        ),
    ):
        with pytest.raises(
            RuntimeError,
            match='Camada SSDMT sem registros validos apos limpeza',
        ):
            task_processar_ssdmt.run(
                'job-ssdmt-5', str(tmp_path / 'arquivo.gdb')
            )


def test_ssdmt_chunk_processa_apenas_janela_configurada(tmp_path):
    rows = [_feature_ssdmt(f'SS-{i}', f'CT-{i}') for i in range(10)]
    dataset = _FakeIterDataset(
        columns=set(REQUIRED_SSDMT_COLUMNS),
        rows=rows,
        crs={'init': 'epsg:3857'},
    )

    class _FakeTransformer:
        def transform(self, x, y, z=None):
            return (x, y)

    with (
        patch(f'{TASK_MODULE}.fiona.open', return_value=dataset),
        patch(f'{TASK_MODULE}.pyproj.CRS.from_user_input', return_value='EPSG:3857'),
        patch(
            f'{TASK_MODULE}.pyproj.Transformer.from_crs',
            return_value=_FakeTransformer(),
        ),
    ):
        result = task_processar_ssdmt_chunk.run(
            'job-ssdmt-chunk',
            str(tmp_path / 'arquivo.gdb'),
            1,
            3,
            4,
        )

    assert result['layer'] == 'SSDMT_CHUNK'
    assert result['chunk_index'] == 1
    assert result['total_lidos'] == 4
    assert result['total'] == 4
    assert result['window']['start_index'] == 3
    assert result['window']['size'] == 4

    tabular_path = result['ssdmt_tabular']['path']
    with open(tabular_path, encoding='utf-8') as tabular_file:
        first_tabular_line = tabular_file.readline().strip()
    assert json.loads(first_tabular_line)['cod_id'] == 'SS-3'

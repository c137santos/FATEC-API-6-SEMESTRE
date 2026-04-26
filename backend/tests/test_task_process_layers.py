import json
from unittest.mock import patch

import pytest

from backend.tasks.task_process_layers import (
    REQUIRED_CTMT_COLUMNS,
    REQUIRED_CONJ_COLUMNS,
    REQUIRED_SSDMT_COLUMNS,
    SSDMT_BATCH_SIZE,
    REQUIRED_UNSEMT_COLUMNS,
    task_finalizar,
    task_processar_ctmt,
    task_processar_conj,
    task_processar_ssdmt_chunk,
    task_processar_ssdmt,
    task_processar_unsemt,
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
    def __init__(
        self, columns: set[str], rows: list[dict], crs=None, crs_wkt=None
    ):
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


def _feature_ssdmt(
    cod_id, ctmt, geometry=None, conj='CJ', comp=10, dist='404'
):
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


_NO_GEOMETRY = object()


def _feature_unsemt(
    cod_id, conj='CJ', tip_unid='32', sit_ativ='AT', geometry=_NO_GEOMETRY
):
    if geometry is _NO_GEOMETRY:
        geometry = {'type': 'Point', 'coordinates': [-54.59809, -22.79093]}
    return {
        'properties': {
            'COD_ID': cod_id,
            'CONJ': conj,
            'TIP_UNID': tip_unid,
            'SIT_ATIV': sit_ativ,
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
    assert record['COD_ID'] == 'CT-01'
    assert record['NOME'] == 'Centro'
    assert record['DIST'] == '404'
    assert record['ENE_01'] == 100
    assert record['PERD_A3a'] == 1.1
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
    assert result['records'][0]['COD_ID'] == 'CT-VALIDO'
    assert result['records'][0]['NOME'] == 'Sul'


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
        patch(
            f'{TASK_MODULE}.pyproj.CRS.from_user_input',
            return_value='EPSG:3857',
        ),
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
        patch(
            f'{TASK_MODULE}.pyproj.CRS.from_user_input',
            return_value='EPSG:3857',
        ),
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
        patch(
            f'{TASK_MODULE}.pyproj.CRS.from_user_input',
            return_value='EPSG:3857',
        ),
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
        patch(
            f'{TASK_MODULE}.pyproj.CRS.from_user_input',
            return_value='EPSG:3857',
        ),
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
        patch(
            f'{TASK_MODULE}.pyproj.CRS.from_user_input',
            return_value='EPSG:3857',
        ),
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


def test_unsemt_retorna_records_com_colunas_necessarias():
    dataset = _FakeDataset(
        columns=set(REQUIRED_UNSEMT_COLUMNS),
        rows=[
            _feature_unsemt('UN-01', conj='CJ1'),
            _feature_unsemt('UN-02', conj='CJ2'),
        ],
    )

    with patch(f'{TASK_MODULE}.fiona.open', return_value=dataset):
        result = task_processar_unsemt.run('job-unsemt-1', '/tmp/arquivo.gdb')

    assert result['layer'] == 'UNSEMT'
    assert result['job_id'] == 'job-unsemt-1'
    assert result['total'] == 2
    assert result['descartados'] == 0

    record = result['records'][0]
    assert record['cod_id'] == 'UN-01'
    assert record['conj'] == 'CJ1'
    assert record['coordinates'] == (-54.59809, -22.79093)
    assert record['job_id'] == 'job-unsemt-1'


def test_unsemt_descarta_registro_sem_cod_id():
    dataset = _FakeDataset(
        columns=set(REQUIRED_UNSEMT_COLUMNS),
        rows=[
            _feature_unsemt(None),
            _feature_unsemt('UN-VALIDO', conj='CJ1'),
        ],
    )

    with patch(f'{TASK_MODULE}.fiona.open', return_value=dataset):
        result = task_processar_unsemt.run('job-unsemt-2', '/tmp/arquivo.gdb')

    assert result['total'] == 1
    assert result['descartados'] == 1
    assert result['records'][0]['cod_id'] == 'UN-VALIDO'


def test_unsemt_descarta_registro_com_tip_unid_diferente():
    dataset = _FakeDataset(
        columns=set(REQUIRED_UNSEMT_COLUMNS),
        rows=[
            _feature_unsemt('UN-01', tip_unid='99'),
            _feature_unsemt('UN-02', tip_unid='32'),
        ],
    )

    with patch(f'{TASK_MODULE}.fiona.open', return_value=dataset):
        result = task_processar_unsemt.run('job-unsemt-3', '/tmp/arquivo.gdb')

    assert result['total'] == 1
    assert result['descartados'] == 1
    assert result['records'][0]['cod_id'] == 'UN-02'


def test_unsemt_descarta_registro_com_sit_ativ_diferente():
    dataset = _FakeDataset(
        columns=set(REQUIRED_UNSEMT_COLUMNS),
        rows=[
            _feature_unsemt('UN-01', sit_ativ='DE'),
            _feature_unsemt('UN-02', sit_ativ='AT'),
        ],
    )

    with patch(f'{TASK_MODULE}.fiona.open', return_value=dataset):
        result = task_processar_unsemt.run('job-unsemt-4', '/tmp/arquivo.gdb')

    assert result['total'] == 1
    assert result['descartados'] == 1
    assert result['records'][0]['cod_id'] == 'UN-02'


def test_unsemt_lanca_erro_quando_faltam_colunas():
    dataset = _FakeDataset(
        columns={'COD_ID', 'CONJ'},
        rows=[_feature_unsemt('UN-01')],
    )

    with patch(f'{TASK_MODULE}.fiona.open', return_value=dataset):
        with pytest.raises(RuntimeError, match='Camada UNSEMT sem colunas'):
            task_processar_unsemt.run('job-unsemt-5', '/tmp/arquivo.gdb')


def test_unsemt_lanca_erro_sem_registros_validos():
    dataset = _FakeDataset(
        columns=set(REQUIRED_UNSEMT_COLUMNS),
        rows=[
            _feature_unsemt(None),
            _feature_unsemt('UN-01', tip_unid='99'),
        ],
    )

    with patch(f'{TASK_MODULE}.fiona.open', return_value=dataset):
        with pytest.raises(
            RuntimeError,
            match='Camada UNSEMT sem registros validos apos limpeza',
        ):
            task_processar_unsemt.run('job-unsemt-6', '/tmp/arquivo.gdb')


def test_unsemt_descarta_quando_sem_geometry():
    dataset = _FakeDataset(
        columns=set(REQUIRED_UNSEMT_COLUMNS),
        rows=[
            _feature_unsemt(
                'UN-01', tip_unid='32', sit_ativ='AT', geometry=None
            ),
            _feature_unsemt('UN-02', tip_unid='32', sit_ativ='AT'),
        ],
    )
    with patch(f'{TASK_MODULE}.fiona.open', return_value=dataset):
        result = task_processar_unsemt.run('job-unsemt-7', '/tmp/arquivo.gdb')

    assert result['descartados'] >= 1
    assert all(r['cod_id'] != 'UN-01' for r in result['records'])


def test_deve_persistir_unsemt_quando_presente():
    results = [
        {'layer': 'UNSEMT', 'records': [{'cod_id': 1}], 'descartados': 2}
    ]

    job_id = 'job-123'
    processed_at = '2024-01-01T00:00:00'

    with patch(
        'backend.tasks.task_process_layers._persist_unsemt'
    ) as mock_persist:
        mock_persist.return_value = 1

        unsemt_result = next(
            (r for r in (results or []) if r.get('layer') == 'UNSEMT'), None
        )

        if unsemt_result:
            _ = mock_persist(
                records=unsemt_result['records'],
                job_id=job_id,
                descartados=unsemt_result['descartados'],
                processed_at=processed_at,
            )

        mock_persist.assert_called_once_with(
            records=[{'cod_id': 1}],
            job_id=job_id,
            descartados=2,
            processed_at=processed_at,
        )


class _FakeMongoCollection:
    def __init__(self):
        self.docs = []
        self.indexes = []
        self.updates = []
        self.replaced = []
        self.fail_on_insert = False
        self.fail_on_replace = False

    def create_index(self, keys, **kwargs):
        self.indexes.append((keys, kwargs))

    def delete_many(self, query):
        job_id = query.get('job_id')
        self.docs = [d for d in self.docs if d.get('job_id') != job_id]

    def insert_many(self, docs, ordered=False):
        if self.fail_on_insert:
            raise RuntimeError('falha insert_many')
        self.docs.extend(docs)

    def replace_one(self, query, doc, upsert=False):
        if self.fail_on_replace:
            raise RuntimeError('falha replace_one')
        self.delete_many(query)
        self.docs.append(doc)
        self.replaced.append((query, doc, upsert))

    def update_one(self, query, update, upsert=False):
        self.updates.append((query, update, upsert))


def test_task_finalizar_persiste_ssdmt_full_em_mongo(tmp_path):
    tabular_path = tmp_path / 'job-1_ssdmt_tabular.ndjson'
    geo_path = tmp_path / 'job-1_ssdmt_geo.ndjson'

    tabular_path.write_text(
        '\n'.join([
            json.dumps({
                'cod_id': 'SS-1',
                'ctmt': 'CT-1',
                'conj': '12807',
                'comp': 10,
                'dist': '404',
                'job_id': 'job-1',
            }),
            json.dumps({
                'cod_id': 'SS-2',
                'ctmt': 'CT-2',
                'conj': '12808',
                'comp': 20,
                'dist': '404',
                'job_id': 'job-1',
            }),
        ])
        + '\n',
        encoding='utf-8',
    )
    geo_path.write_text(
        '\n'.join([
            json.dumps({
                'type': 'Feature',
                'properties': {
                    'cod_id': 'SS-1',
                    'ctmt': 'CT-1',
                    'conj': '12807',
                    'comp': 10,
                    'dist': '404',
                    'job_id': 'job-1',
                },
                'geometry': {'type': 'Point', 'coordinates': [0, 0]},
            }),
            json.dumps({
                'type': 'Feature',
                'properties': {
                    'cod_id': 'SS-2',
                    'ctmt': 'CT-2',
                    'conj': '12808',
                    'comp': 20,
                    'dist': '404',
                    'job_id': 'job-1',
                },
                'geometry': {'type': 'Point', 'coordinates': [1, 1]},
            }),
        ])
        + '\n',
        encoding='utf-8',
    )

    jobs_col = _FakeMongoCollection()
    ctmt_col = _FakeMongoCollection()
    tab_col = _FakeMongoCollection()
    geo_col = _FakeMongoCollection()

    collections = {
        'jobs': jobs_col,
        'circuitos_mt': ctmt_col,
        'conjuntos': _FakeMongoCollection(),
        'segmentos_mt_tabular': tab_col,
        'segmentos_mt_geo': geo_col,
    }

    with patch(
        f'{TASK_MODULE}._get_collection',
        side_effect=lambda name: collections[name],
    ):
        result = task_finalizar.run(
            [
                {
                    'layer': 'SSDMT',
                    'job_id': 'job-1',
                    'ssdmt_tabular': {
                        'path': str(tabular_path),
                        'records_count': 2,
                    },
                    'ssdmt_geo': {'path': str(geo_path), 'records_count': 2},
                    'descartados': 1,
                    'falhas_reprojecao': 0,
                }
            ],
            'job-1',
            '/tmp/a.zip',
            '/tmp',
        )

    assert result['status'] == 'completed'
    assert result['ssdmt_total'] == 2
    assert len(tab_col.docs) == 2
    assert len(geo_col.docs) == 2
    assert tab_col.docs[0]['COD_ID'] == 'SS-1'
    assert tab_col.docs[0]['CTMT'] == 'CT-1'
    assert geo_col.docs[0]['geometry']['type'] == 'Point'
    assert any(
        idx[0] == [('job_id', 1), ('COD_ID', 1)] and idx[1].get('unique')
        for idx in tab_col.indexes
    )
    assert any(idx[0] == [('geometry', '2dsphere')] for idx in geo_col.indexes)
    assert not tabular_path.exists()
    assert not geo_path.exists()


def test_task_finalizar_consolida_ssdmt_chunk(tmp_path):
    tab_0 = tmp_path / 'job-2_ssdmt_tabular_chunk_00000.ndjson'
    geo_0 = tmp_path / 'job-2_ssdmt_geo_chunk_00000.ndjson'
    tab_1 = tmp_path / 'job-2_ssdmt_tabular_chunk_00001.ndjson'
    geo_1 = tmp_path / 'job-2_ssdmt_geo_chunk_00001.ndjson'

    tab_0.write_text(
        json.dumps({
            'cod_id': 'SS-1',
            'ctmt': 'CT-1',
            'conj': 'A',
            'comp': 1,
            'dist': '404',
        })
        + '\n',
        encoding='utf-8',
    )
    tab_1.write_text(
        json.dumps({
            'cod_id': 'SS-2',
            'ctmt': 'CT-2',
            'conj': 'B',
            'comp': 2,
            'dist': '404',
        })
        + '\n',
        encoding='utf-8',
    )
    geo_0.write_text(
        json.dumps({
            'type': 'Feature',
            'properties': {
                'cod_id': 'SS-1',
                'ctmt': 'CT-1',
                'conj': 'A',
                'comp': 1,
                'dist': '404',
            },
            'geometry': {'type': 'Point', 'coordinates': [0, 0]},
        })
        + '\n',
        encoding='utf-8',
    )
    geo_1.write_text(
        json.dumps({
            'type': 'Feature',
            'properties': {
                'cod_id': 'SS-2',
                'ctmt': 'CT-2',
                'conj': 'B',
                'comp': 2,
                'dist': '404',
            },
            'geometry': {'type': 'Point', 'coordinates': [1, 1]},
        })
        + '\n',
        encoding='utf-8',
    )

    jobs_col = _FakeMongoCollection()
    collections = {
        'jobs': jobs_col,
        'circuitos_mt': _FakeMongoCollection(),
        'conjuntos': _FakeMongoCollection(),
        'segmentos_mt_tabular': _FakeMongoCollection(),
        'segmentos_mt_geo': _FakeMongoCollection(),
    }

    with patch(
        f'{TASK_MODULE}._get_collection',
        side_effect=lambda name: collections[name],
    ):
        result = task_finalizar.run(
            [
                {
                    'layer': 'SSDMT_CHUNK',
                    'job_id': 'job-2',
                    'ssdmt_tabular': {'path': str(tab_0), 'records_count': 1},
                    'ssdmt_geo': {'path': str(geo_0), 'records_count': 1},
                    'descartados': 1,
                    'falhas_reprojecao': 0,
                },
                {
                    'layer': 'SSDMT_CHUNK',
                    'job_id': 'job-2',
                    'ssdmt_tabular': {'path': str(tab_1), 'records_count': 1},
                    'ssdmt_geo': {'path': str(geo_1), 'records_count': 1},
                    'descartados': 2,
                    'falhas_reprojecao': 1,
                },
            ],
            'job-2',
            '/tmp/a.zip',
            '/tmp',
        )

    assert result['status'] == 'completed'
    assert result['ssdmt_total'] == 2
    assert len(collections['segmentos_mt_tabular'].docs) == 2
    assert len(collections['segmentos_mt_geo'].docs) == 2

    jobs_update = jobs_col.updates[-1][1]['$set']
    assert jobs_update['ssdmt_descartados'] == 3
    assert jobs_update['ssdmt_falhas_reprojecao'] == 1


def test_task_finalizar_falha_no_ssdmt_faz_rollback(tmp_path):
    tabular_path = tmp_path / 'job-3_ssdmt_tabular.ndjson'
    geo_path = tmp_path / 'job-3_ssdmt_geo.ndjson'
    tabular_path.write_text(
        json.dumps({
            'cod_id': 'SS-1',
            'ctmt': 'CT-1',
            'conj': 'A',
            'comp': 1,
            'dist': '404',
        })
        + '\n',
        encoding='utf-8',
    )
    geo_path.write_text(
        json.dumps({
            'type': 'Feature',
            'properties': {
                'cod_id': 'SS-1',
                'ctmt': 'CT-1',
                'conj': 'A',
                'comp': 1,
                'dist': '404',
            },
            'geometry': {'type': 'Point', 'coordinates': [0, 0]},
        })
        + '\n',
        encoding='utf-8',
    )

    jobs_col = _FakeMongoCollection()
    tab_col = _FakeMongoCollection()
    geo_col = _FakeMongoCollection()
    tab_col.fail_on_insert = True

    collections = {
        'jobs': jobs_col,
        'circuitos_mt': _FakeMongoCollection(),
        'conjuntos': _FakeMongoCollection(),
        'segmentos_mt_tabular': tab_col,
        'segmentos_mt_geo': geo_col,
    }

    with patch(
        f'{TASK_MODULE}._get_collection',
        side_effect=lambda name: collections[name],
    ):
        with pytest.raises(RuntimeError, match='falha insert_many'):
            task_finalizar.run(
                [
                    {
                        'layer': 'SSDMT',
                        'job_id': 'job-3',
                        'ssdmt_tabular': {
                            'path': str(tabular_path),
                            'records_count': 1,
                        },
                        'ssdmt_geo': {
                            'path': str(geo_path),
                            'records_count': 1,
                        },
                        'descartados': 0,
                        'falhas_reprojecao': 0,
                    }
                ],
                'job-3',
                '/tmp/a.zip',
                '/tmp',
            )

    assert tab_col.docs == []
    assert geo_col.docs == []
    assert jobs_col.updates[-1][1]['$set']['status'] == 'failed'


def test_task_finalizar_persiste_conj_para_notebooks():
    jobs_col = _FakeMongoCollection()
    conj_col = _FakeMongoCollection()

    collections = {
        'jobs': jobs_col,
        'circuitos_mt': _FakeMongoCollection(),
        'conjuntos': conj_col,
        'segmentos_mt_tabular': _FakeMongoCollection(),
        'segmentos_mt_geo': _FakeMongoCollection(),
    }

    with patch(
        f'{TASK_MODULE}._get_collection',
        side_effect=lambda name: collections[name],
    ):
        result = task_finalizar.run(
            [
                {
                    'layer': 'CONJ',
                    'job_id': 'job-conj-1',
                    'records': [
                        {'cod_id': 12807, 'nome': 'CONJ A', 'dist': '404'},
                        {'cod_id': 12808, 'nome': 'CONJ B', 'dist': '404'},
                    ],
                    'descartados': 1,
                }
            ],
            'job-conj-1',
            '/tmp/a.zip',
            '/tmp',
        )

    assert result['status'] == 'completed'
    assert result['conj_total'] == 2
    assert len(conj_col.docs) == 1
    assert conj_col.docs[0]['job_id'] == 'job-conj-1'
    assert conj_col.docs[0]['total'] == 2
    assert conj_col.docs[0]['descartados'] == 1

    jobs_update = jobs_col.updates[-1][1]['$set']
    assert jobs_update['conj_total'] == 2


def test_task_finalizar_falha_no_conj_faz_rollback():
    jobs_col = _FakeMongoCollection()
    conj_col = _FakeMongoCollection()
    conj_col.fail_on_replace = True
    ssdmt_tab_col = _FakeMongoCollection()
    ssdmt_geo_col = _FakeMongoCollection()

    collections = {
        'jobs': jobs_col,
        'circuitos_mt': _FakeMongoCollection(),
        'conjuntos': conj_col,
        'segmentos_mt_tabular': ssdmt_tab_col,
        'segmentos_mt_geo': ssdmt_geo_col,
    }

    with patch(
        f'{TASK_MODULE}._get_collection',
        side_effect=lambda name: collections[name],
    ):
        with pytest.raises(RuntimeError, match='falha replace_one'):
            task_finalizar.run(
                [
                    {
                        'layer': 'CONJ',
                        'job_id': 'job-conj-2',
                        'records': [
                            {'cod_id': 99999, 'nome': 'X', 'dist': '404'}
                        ],
                        'descartados': 0,
                    }
                ],
                'job-conj-2',
                '/tmp/a.zip',
                '/tmp',
            )

    assert jobs_col.updates[-1][1]['$set']['status'] == 'failed'
    assert ssdmt_tab_col.docs == []
    assert ssdmt_geo_col.docs == []

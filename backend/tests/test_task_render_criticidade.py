import pytest
from unittest.mock import MagicMock, patch
from celery.exceptions import Retry
from shapely.geometry import LineString, mapping

from backend.tasks.task_render_criticidade import (
    _cor_score,
    task_render_mapa_calor,
    task_render_tabela_score,
)

PATCH_DB = 'backend.tasks.task_render_criticidade.get_mongo_sync_db'
PATCH_SAVEFIG = 'backend.tasks.task_render_criticidade.plt.savefig'
PATCH_CLOSE = 'backend.tasks.task_render_criticidade.plt.close'
PATCH_OUTPUT_DIR = 'backend.tasks.task_render_criticidade._output_dir'

_SCORE_DOC = {
    'distribuidora': 'ENEL RJ',
    'ano': 2024,
    'score_criticidade': 25.0,
    'quantidade_conjuntos': 2,
}

_MAPA_DOC = {
    'distribuidora': 'ENEL RJ',
    'ano': 2024,
    'job_id': 'gdb-job-1',
    'conjuntos': [
        {
            'ide_conj': '100',
            'dsc_conj': 'CONJ A',
            'dec_realizado': 15.0,
            'dec_limite': 10.0,
            'fec_realizado': 12.0,
            'fec_limite': 10.0,
            'desvio_dec': 50.0,
            'desvio_fec': 20.0,
            'score_criticidade': 70.0,
            'categoria': 'Vermelho',
        },
        {
            'ide_conj': '200',
            'dsc_conj': 'CONJ B',
            'dec_realizado': 5.0,
            'dec_limite': 10.0,
            'fec_realizado': 3.0,
            'fec_limite': 10.0,
            'desvio_dec': 0.0,
            'desvio_fec': 0.0,
            'score_criticidade': 0.0,
            'categoria': 'Verde',
        },
    ],
}

_LINE_GEOM = mapping(LineString([(0, 0), (1, 1)]))


def _make_db(score_doc=_SCORE_DOC, mapa_doc=_MAPA_DOC, geo_docs=None):
    db = MagicMock()
    score_col = MagicMock()
    score_col.find_one.return_value = score_doc
    mapa_col = MagicMock()
    mapa_col.find_one.return_value = mapa_doc
    geo_col = MagicMock()
    geo_col.find.return_value = geo_docs if geo_docs is not None else []

    def _getitem(name):
        return {
            'score_criticidade': score_col,
            'mapa_criticidade': mapa_col,
            'segmentos_mt_geo': geo_col,
        }.get(name, MagicMock())

    db.__getitem__.side_effect = _getitem
    return db


# ---------------------------------------------------------------------------
# _cor_score
# ---------------------------------------------------------------------------


def test_cor_score_zero_retorna_verde():
    assert _cor_score(0) == '#c8e6c9'


def test_cor_score_ate_50_retorna_amarelo():
    assert _cor_score(0.001) == '#fff9c4'
    assert _cor_score(25) == '#fff9c4'
    assert _cor_score(50) == '#fff9c4'


def test_cor_score_acima_50_retorna_vermelho():
    assert _cor_score(50.001) == '#ffcdd2'
    assert _cor_score(1000) == '#ffcdd2'


# ---------------------------------------------------------------------------
# task_render_tabela_score
# ---------------------------------------------------------------------------


def test_render_tabela_retry_quando_score_ausente():
    db = _make_db(score_doc=None)
    with patch(PATCH_DB, return_value=db):
        with pytest.raises(Retry):
            task_render_tabela_score.run('job-1', 'ENEL RJ', 2024)


def test_render_tabela_retry_quando_mapa_ausente():
    db = _make_db(mapa_doc=None)
    with patch(PATCH_DB, return_value=db):
        with pytest.raises(Retry):
            task_render_tabela_score.run('job-1', 'ENEL RJ', 2024)


def test_render_tabela_sem_conjuntos_retorna_skipped():
    db = _make_db(mapa_doc={**_MAPA_DOC, 'conjuntos': []})
    with patch(PATCH_DB, return_value=db):
        result = task_render_tabela_score.run('job-1', 'ENEL RJ', 2024)
    assert result['status'] == 'skipped'
    assert result['reason'] == 'no_conjuntos'


def test_render_tabela_happy_path(tmp_path):
    db = _make_db()
    with (
        patch(PATCH_DB, return_value=db),
        patch(PATCH_SAVEFIG),
        patch(PATCH_CLOSE),
        patch(PATCH_OUTPUT_DIR, return_value=tmp_path),
    ):
        result = task_render_tabela_score.run('job-1', 'ENEL RJ', 2024)

    assert result['status'] == 'done'
    assert result['job_id'] == 'job-1'
    assert 'tabela_score_ENEL RJ_2024' in result['path']


def test_render_tabela_salva_arquivo_no_caminho_correto(tmp_path):
    db = _make_db()
    with (
        patch(PATCH_DB, return_value=db),
        patch(PATCH_SAVEFIG) as mock_savefig,
        patch(PATCH_CLOSE),
        patch(PATCH_OUTPUT_DIR, return_value=tmp_path),
    ):
        task_render_tabela_score.run('job-1', 'ENEL RJ', 2024)

    saved_path = mock_savefig.call_args[0][0]
    assert str(saved_path).endswith('tabela_score_ENEL RJ_2024.png')


def test_render_tabela_usa_nome_da_distribuidora_do_score_doc(tmp_path):
    """O título usa o nome do score_doc, não o parâmetro distribuidora."""
    score_doc_custom = {**_SCORE_DOC, 'distribuidora': 'ENEL_RJ_CUSTOM'}
    db = _make_db(score_doc=score_doc_custom)
    with (
        patch(PATCH_DB, return_value=db),
        patch(PATCH_SAVEFIG) as mock_savefig,
        patch(PATCH_CLOSE),
        patch(PATCH_OUTPUT_DIR, return_value=tmp_path),
    ):
        task_render_tabela_score.run('job-1', 'ENEL RJ', 2024)

    saved_path = mock_savefig.call_args[0][0]
    assert 'ENEL_RJ_CUSTOM' in str(saved_path)


# ---------------------------------------------------------------------------
# task_render_mapa_calor
# ---------------------------------------------------------------------------


def test_render_mapa_retry_quando_score_ausente():
    db = _make_db(score_doc=None)
    with patch(PATCH_DB, return_value=db):
        with pytest.raises(Retry):
            task_render_mapa_calor.run('job-1', 'ENEL RJ', 2024)


def test_render_mapa_retry_quando_mapa_ausente():
    db = _make_db(mapa_doc=None)
    with patch(PATCH_DB, return_value=db):
        with pytest.raises(Retry):
            task_render_mapa_calor.run('job-1', 'ENEL RJ', 2024)


def test_render_mapa_retry_quando_job_id_ausente():
    db = _make_db(mapa_doc={**_MAPA_DOC, 'job_id': None})
    with patch(PATCH_DB, return_value=db):
        with pytest.raises(Retry):
            task_render_mapa_calor.run('job-1', 'ENEL RJ', 2024)


def test_render_mapa_sem_categorias_retorna_skipped():
    """ide_conj não conversível para int → categoria_por_conj vazia → skipped."""
    mapa_inv = {**_MAPA_DOC, 'conjuntos': [{'ide_conj': 'nao-inteiro', 'categoria': 'Verde'}]}
    db = _make_db(mapa_doc=mapa_inv)
    with patch(PATCH_DB, return_value=db):
        result = task_render_mapa_calor.run('job-1', 'ENEL RJ', 2024)
    assert result['status'] == 'skipped'
    assert result['reason'] == 'no_categorias'


def test_render_mapa_sem_geometrias_retorna_skipped():
    db = _make_db(geo_docs=[])
    with patch(PATCH_DB, return_value=db):
        result = task_render_mapa_calor.run('job-1', 'ENEL RJ', 2024)
    assert result['status'] == 'skipped'
    assert result['reason'] == 'no_geometries'


def test_render_mapa_geometria_invalida_descartada_sem_quebrar():
    """Documento com geometria corrompida deve ser ignorado silenciosamente."""
    geo_docs = [
        {'CONJ': 100, 'geometry': None},           # geometry None
        {'CONJ': None, 'geometry': _LINE_GEOM},    # CONJ None
    ]
    db = _make_db(geo_docs=geo_docs)
    with patch(PATCH_DB, return_value=db):
        result = task_render_mapa_calor.run('job-1', 'ENEL RJ', 2024)
    assert result['status'] == 'skipped'
    assert result['reason'] == 'no_geometries'


def test_render_mapa_happy_path(tmp_path):
    geo_docs = [
        {'CONJ': 100, 'geometry': _LINE_GEOM},
        {'CONJ': 200, 'geometry': _LINE_GEOM},
    ]
    db = _make_db(geo_docs=geo_docs)
    with (
        patch(PATCH_DB, return_value=db),
        patch(PATCH_SAVEFIG),
        patch(PATCH_CLOSE),
        patch(PATCH_OUTPUT_DIR, return_value=tmp_path),
    ):
        result = task_render_mapa_calor.run('job-1', 'ENEL RJ', 2024)

    assert result['status'] == 'done'
    assert result['job_id'] == 'job-1'
    assert 'mapa_calor_ENEL RJ_2024' in result['path']


def test_render_mapa_salva_arquivo_no_caminho_correto(tmp_path):
    geo_docs = [{'CONJ': 100, 'geometry': _LINE_GEOM}]
    db = _make_db(geo_docs=geo_docs)
    with (
        patch(PATCH_DB, return_value=db),
        patch(PATCH_SAVEFIG) as mock_savefig,
        patch(PATCH_CLOSE),
        patch(PATCH_OUTPUT_DIR, return_value=tmp_path),
    ):
        task_render_mapa_calor.run('job-1', 'ENEL RJ', 2024)

    saved_path = mock_savefig.call_args[0][0]
    assert str(saved_path).endswith('mapa_calor_ENEL RJ_2024.png')

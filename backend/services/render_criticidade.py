import logging
from functools import lru_cache
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use('Agg')
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from shapely.geometry import shape

from backend.services.criticidade import get_mongo_collection

logger = logging.getLogger(__name__)

_CATEGORIA_COR = {
    'Verde': '#4CAF50',
    'Laranja': '#FF9800',
    'Vermelho': '#F44336',
}


def _cor_score(score: float) -> str:
    if score == 0:
        return '#c8e6c9'
    if score <= 50:
        return '#fff9c4'
    return '#ffcdd2'


@lru_cache(maxsize=None)
def _output_dir() -> Path:
    path = Path(__file__).resolve().parent.parent.parent / 'output' / 'images'
    path.mkdir(parents=True, exist_ok=True)
    return path


async def _buscar_score_criticidade(
    distribuidora: str, ano: int
) -> dict | None:
    doc = await get_mongo_collection('score_criticidade').find_one(
        {'distribuidora': distribuidora.upper(), 'ano': ano},
        {'_id': 0},
    )
    return doc


async def render_tabela_score_criticidade(
    distribuidora: str, ano: int
) -> Path:
    score_doc = await _buscar_score_criticidade(distribuidora, ano)
    if not score_doc:
        raise ValueError(
            f'Score não encontrado para distribuidora={distribuidora} ano={ano}'
        )

    mapa_doc = await get_mongo_collection('mapa_criticidade').find_one(
        {'distribuidora': distribuidora.upper(), 'ano': ano}, {'_id': 0}
    )
    if not mapa_doc:
        raise ValueError(
            f'Mapa de criticidade não encontrado para distribuidora={distribuidora} ano={ano}'
        )

    conjuntos = mapa_doc.get('conjuntos', [])
    if not conjuntos:
        raise ValueError('Nenhum conjunto disponível para renderizar a tabela')

    colunas = [
        '#',
        'Conjunto',
        'DEC Real.',
        'DEC Lim.',
        'FEC Real.',
        'FEC Lim.',
        'Desv. DEC %',
        'Desv. FEC %',
        'Score',
    ]
    linhas = [
        [
            rank,
            c.get('dsc_conj') or c.get('ide_conj', ''),
            f'{c.get("dec_realizado", 0):.2f}',
            f'{c.get("dec_limite", 0):.2f}',
            f'{c.get("fec_realizado", 0):.2f}',
            f'{c.get("fec_limite", 0):.2f}',
            f'{c.get("desvio_dec", 0):.2f}',
            f'{c.get("desvio_fec", 0):.2f}',
            f'{c.get("score_criticidade", 0):.2f}',
        ]
        for rank, c in enumerate(conjuntos, start=1)
    ]

    n_rows = len(linhas)
    fig_height = max(4, 0.45 * n_rows + 1.5)
    fig, ax = plt.subplots(figsize=(18, fig_height))
    ax.set_axis_off()

    table = ax.table(
        cellText=linhas, colLabels=colunas, loc='center', cellLoc='center'
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.auto_set_column_width(col=list(range(len(colunas))))

    for col_idx in range(len(colunas)):
        cell = table[0, col_idx]
        cell.set_facecolor('#263238')
        cell.set_text_props(color='white', fontweight='bold')

    score_col_idx = len(colunas) - 1
    for row_idx, conj in enumerate(conjuntos, start=1):
        score = conj.get('score_criticidade', 0)
        table[row_idx, score_col_idx].set_facecolor(
            mcolors.to_rgba(_cor_score(score))
        )

    sig = score_doc.get('distribuidora', distribuidora.upper())
    ax.set_title(
        f'Score de Criticidade — {sig} ({ano})\n'
        f'Score médio: {score_doc.get("score_criticidade", 0):.2f} | '
        f'Total conjuntos: {score_doc.get("quantidade_conjuntos", n_rows)}',
        fontsize=11,
        pad=12,
    )

    out_path = _output_dir() / f'tabela_score_{sig}_{ano}.png'
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info('Tabela score_criticidade salva em %s', out_path)
    return out_path


async def render_mapa_calor_criticidade(distribuidora: str, ano: int) -> Path:
    score_doc = await _buscar_score_criticidade(distribuidora, ano)
    if not score_doc:
        raise ValueError(
            f'Score não encontrado para distribuidora={distribuidora} ano={ano}'
        )

    mapa_doc = await get_mongo_collection('mapa_criticidade').find_one(
        {'distribuidora': distribuidora.upper(), 'ano': ano},
        {'_id': 0, 'job_id': 1, 'conjuntos': 1},
    )
    job_id = mapa_doc.get('job_id') if mapa_doc else None
    if not job_id:
        raise ValueError(
            f'job_id não encontrado para distribuidora={distribuidora} ano={ano}'
        )

    categoria_por_conj: dict[int, str] = {}
    for conj in (mapa_doc.get('conjuntos', []) if mapa_doc else []):
        try:
            ide = int(conj['ide_conj'])
        except (KeyError, ValueError, TypeError):
            continue
        categoria_por_conj[ide] = conj.get('categoria', 'Verde')

    if not categoria_por_conj:
        raise ValueError('Nenhum conjunto com categoria encontrado')

    features = []
    async for doc in get_mongo_collection('segmentos_mt_geo').find(
        {'job_id': job_id, 'CONJ': {'$in': list(categoria_por_conj.keys())}},
        {'_id': 0, 'CONJ': 1, 'geometry': 1},
    ):
        geom_dict = doc.get('geometry')
        conj_id = doc.get('CONJ')
        if not geom_dict or conj_id is None:
            continue
        try:
            features.append({
                'geometry': shape(geom_dict),
                'categoria': categoria_por_conj.get(int(conj_id), 'Verde'),
            })
        except Exception:
            logger.debug('Geometria inválida descartada. CONJ=%s', conj_id)

    if not features:
        raise ValueError('Nenhuma geometria disponível para renderizar o mapa')

    gdf = gpd.GeoDataFrame(features, geometry='geometry', crs='EPSG:4326')
    gdf['cor'] = gdf['categoria'].map(_CATEGORIA_COR)

    sig = score_doc.get('distribuidora', distribuidora.upper())

    fig, ax = plt.subplots(1, 1, figsize=(15, 15))
    gdf.plot(color=gdf['cor'], linewidth=0.8, ax=ax, edgecolor='0.8')
    ax.set_title(f'Heatmap de Criticidade — {sig} ({ano})', fontsize=15)
    ax.set_axis_off()
    ax.legend(
        handles=[
            Patch(
                facecolor=_CATEGORIA_COR['Verde'],
                label='0% (Dentro ou próximo da meta)',
            ),
            Patch(
                facecolor=_CATEGORIA_COR['Laranja'],
                label='0-10% (Demandam atenção)',
            ),
            Patch(
                facecolor=_CATEGORIA_COR['Vermelho'],
                label='>10% (Alta criticidade)',
            ),
        ],
        title=f'Score de Criticidade ({ano})',
        loc='lower right',
    )

    out_path = _output_dir() / f'mapa_calor_{sig}_{ano}.png'
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info('Mapa de calor salvo em %s', out_path)
    return out_path

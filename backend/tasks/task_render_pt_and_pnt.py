import logging
import time
from functools import lru_cache
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from backend.database import get_mongo_sync_db
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

WAIT_COUNTDOWN = 30
MAX_WAIT_RETRIES = 60

_COR_PT = '#4DB6AC'
_COR_PNT = '#1565C0'
_PCT_MIN_LABEL = 8
_MILHARES = 1000


@lru_cache(maxsize=None)
def _output_dir() -> Path:
    path = Path(__file__).resolve().parent.parent.parent / 'output' / 'images'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _adicionar_labels_percentual(ax, pt_vals, pnt_vals, totais):
    for i, (pt, pnt, total) in enumerate(zip(pt_vals, pnt_vals, totais)):
        if total == 0:
            continue
        pct_pt = pt / total * 100
        pct_pnt = pnt / total * 100
        if pct_pt >= _PCT_MIN_LABEL:
            ax.text(
                pt / 2,
                i,
                f'{pct_pt:.1f}%',
                ha='center',
                va='center',
                fontsize=7,
                color='white',
                fontweight='bold',
                zorder=4,
            )
        if pct_pnt >= _PCT_MIN_LABEL:
            ax.text(
                pt + pnt / 2,
                i,
                f'{pct_pnt:.1f}%',
                ha='center',
                va='center',
                fontsize=7,
                color='white',
                fontweight='bold',
                zorder=4,
            )


def _estilizar_eixos(ax):
    ax.tick_params(axis='x', colors='#555555', labelsize=8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_color('#cccccc')
    ax.grid(axis='x', color='#eeeeee', linewidth=0.8, zorder=0)
    ax.set_xlabel('MWh', fontsize=9, color='#555555')
    ax.xaxis.set_major_formatter(
        mticker.FuncFormatter(
            lambda v, _: (
                f'{v / _MILHARES:.0f}K' if v >= _MILHARES else f'{v:.0f}'
            )
        )
    )


@celery_app.task(name='etl.render_pt_pnt')
def task_render_pt_pnt(
    job_id: str, distribuidora_id: str, sig_agente: str, ano: int
) -> dict:
    logger.info('[task_render_pt_pnt] Inicio. job_id=%s', job_id)

    db = get_mongo_sync_db()
    doc = db['pt_pnt_resultados'].find_one(
        {'job_id': job_id, 'distribuidora_id': distribuidora_id},
        {'_id': 0},
    )

    for attempt in range(MAX_WAIT_RETRIES):
        if doc:
            break
        logger.info('[task_render_pt_pnt] Aguardando dados. tentativa=%d job_id=%s', attempt + 1, job_id)
        time.sleep(WAIT_COUNTDOWN)
        doc = db['pt_pnt_resultados'].find_one(
            {'job_id': job_id, 'distribuidora_id': distribuidora_id},
            {'_id': 0},
        )
    else:
        raise RuntimeError(f'[task_render_pt_pnt] Timeout aguardando dados. job_id={job_id}')

    records = doc.get('records', [])
    if not records:
        logger.warning(
            '[task_render_pt_pnt] Nenhum registro disponível. job_id=%s',
            job_id,
        )
        db['jobs'].update_one(
            {'job_id': job_id},
            {'$set': {'render_paths.pt_pnt': None}},
        )
        return {'job_id': job_id, 'status': 'skipped', 'reason': 'no_records'}

    conjuntos = [r.get('conjunto', '') for r in records][::-1]
    pt_vals = np.array([r.get('pt_mwh', 0.0) for r in records])[::-1]
    pnt_vals = np.array([r.get('pnt_mwh', 0.0) for r in records])[::-1]
    totais = pt_vals + pnt_vals

    fig_height = max(6, len(conjuntos) * 0.55 + 2)
    fig, ax = plt.subplots(figsize=(14, fig_height))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')

    y = np.arange(len(conjuntos))

    ax.barh(y, pt_vals, height=0.5, label='PT (MWh)', color=_COR_PT, zorder=3)
    ax.barh(
        y,
        pnt_vals,
        height=0.5,
        label='PNT (MWh)',
        color=_COR_PNT,
        left=pt_vals,
        zorder=3,
    )

    _adicionar_labels_percentual(ax, pt_vals, pnt_vals, totais)
    _estilizar_eixos(ax)

    ax.set_yticks(y)
    ax.set_yticklabels(conjuntos, fontsize=9, color='#333333')
    ax.legend(
        loc='lower right', fontsize=9, framealpha=0.9, edgecolor='#cccccc'
    )

    ax.set_title(
        f'Gráfico de Perdas Técnicas e Não Técnicas\n'
        f'Todos os conjuntos da Distribuidora {sig_agente}  |  {ano}',
        fontsize=11,
        color='#222222',
        pad=14,
        loc='left',
    )

    plt.tight_layout()

    out_path = _output_dir() / f'pt_pnt_{sig_agente}_{ano}_{job_id}.png'
    plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)

    db['jobs'].update_one(
        {'job_id': job_id},
        {'$set': {'render_paths.pt_pnt': str(out_path)}},
    )

    logger.info(
        '[task_render_pt_pnt] Concluida. job_id=%s path=%s',
        job_id,
        out_path,
    )
    return {'job_id': job_id, 'status': 'done', 'path': str(out_path)}

import logging
from functools import lru_cache
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

from backend.database import get_mongo_sync_db
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

WAIT_COUNTDOWN = 30
MAX_WAIT_RETRIES = 60
BAR_COLOR = '#2196F3'
TEXT_COLOR = '#263238'

@lru_cache(maxsize=None)
def _output_dir() -> Path:
    path = Path(__file__).resolve().parent.parent.parent / 'output' / 'images'
    path.mkdir(parents=True, exist_ok=True)
    return path

@celery_app.task(
    bind=True, 
    max_retries=MAX_WAIT_RETRIES, 
    name='etl.render_grafico_tam'
)
def task_render_grafico_tam(self, job_id: str) -> dict:
    """
    Task síncrona para geração do gráfico TAM com lógica de retentativa.
    """
    logger.info('[task_render_grafico_tam] Início. job_id=%s', job_id)

    db = get_mongo_sync_db()
    
    projection = {
        '_id': 0, 
        'NOME': 1, 
        'CTMT': 1, 
        'COMP_KM': 1, 
        'dist_name': 1
    }
    cursor = db['TAM'].find({'job_id': job_id}, projection)
    dados = list(cursor)

    if not dados:
        logger.info('[task_render_grafico_tam] Dados não encontrados, tentando novamente... job_id=%s', job_id)
        raise self.retry(countdown=WAIT_COUNTDOWN)

    try:
        df = pd.DataFrame(dados)
        
        df['eixo_x'] = df['NOME'].fillna(df['CTMT']).fillna("S/N").astype(str)
        df['eixo_y'] = pd.to_numeric(df['COMP_KM'], errors='coerce').fillna(0)
        
        df = df.sort_values(by='eixo_y', ascending=False).head(10)
        
        titulo_dist = df['dist_name'].iloc[0] if 'dist_name' in df.columns else 'Relatório de Distâncias'

        n_rows = len(df)
        fig, ax = plt.subplots(figsize=(12, 7))

        bars = ax.bar(
            df['eixo_x'], 
            df['eixo_y'], 
            color=BAR_COLOR, 
            alpha=0.85,
            edgecolor='white',
            linewidth=0.5
        )

        ax.set_title(
            f'Top 10 Maiores Trechos (TAM) - {titulo_dist}', 
            fontsize=14, pad=20, fontweight='bold', color=TEXT_COLOR
        )
        
        ax.set_ylabel('Comprimento (KM)', fontsize=11, fontweight='bold', color=TEXT_COLOR)
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.yaxis.grid(True, linestyle='--', alpha=0.4)
        ax.set_axisbelow(True) 

        plt.xticks(rotation=45, ha='right', fontsize=9)

        for bar in bars:
            yval = bar.get_height()
            if yval > 0:
                ax.text(
                    bar.get_x() + bar.get_width()/2, 
                    yval + (df['eixo_y'].max() * 0.01), 
                    f'{yval:.2f}', 
                    ha='center', va='bottom', fontsize=8, fontweight='bold'
                )

        plt.tight_layout()

        out_path = _output_dir() / f'grafico_tam_{job_id}.png'
        plt.savefig(out_path, dpi=150, bbox_inches='tight')
        plt.close(fig)

        logger.info('[task_render_grafico_tam] Concluída. job_id=%s path=%s', job_id, out_path)
        
        return {
            'job_id': job_id, 
            'status': 'done', 
            'path': str(out_path)
        }

    except Exception:
         logger.exception('[task_render_grafico_tam] Erro fatal. job_id=%s', job_id)
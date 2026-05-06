import logging
from functools import lru_cache
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from backend.services.criticidade import get_mongo_collection

logger = logging.getLogger(__name__)

BAR_COLOR = '#2196F3'
TEXT_COLOR = '#263238'

@lru_cache(maxsize=None)
def _output_dir() -> Path:
    """Cache do diretório para evitar recalculate constante de caminhos."""
    path = Path(__file__).resolve().parent.parent.parent / 'output' / 'images'
    path.mkdir(parents=True, exist_ok=True)
    return path

async def render_grafico_barras_tam(job_id: str) -> Path:
    """
    Renderiza gráfico de barras do TAM com performance e estética aprimoradas.
    """
    projection = {
        '_id': 0, 
        'NOME': 1, 
        'CTMT': 1, 
        'COMP_KM': 1, 
        'dist_name': 1
    }
    
    cursor = get_mongo_collection('TAM').find({'job_id': job_id}, projection)
    dados = await cursor.to_list(length=2000)

    if not dados:
        raise ValueError(f'Nenhum dado encontrado para job_id: {job_id}')

    df = pd.DataFrame(dados)
    
    df['eixo_x'] = df['NOME'].fillna(df['CTMT']).fillna("S/N").astype(str)
    df['eixo_y'] = pd.to_numeric(df['COMP_KM'], errors='coerce').fillna(0)
    
    df = df.sort_values(by='eixo_y', ascending=False).head(10)

    titulo_dist = df['dist_name'].iloc[0] if 'dist_name' in df.columns else ''

    n_rows = len(df)

    fig, ax = plt.subplots(figsize=(12, 8))

    bars = ax.bar(
        df['eixo_x'], 
        df['eixo_y'], 
        color=BAR_COLOR, 
        edgecolor='white', 
        linewidth=0.5,
        alpha=0.85
    )

    ax.set_title(
        f'Ranking Top 10 - Maiores Trechos (TAM)\n{titulo_dist}',
        fontsize=14,
        pad=20, 
        fontweight='bold',
        color=TEXT_COLOR
    )
    
    ax.set_ylabel('Comprimento (KM)', fontsize=11, fontweight='bold', color=TEXT_COLOR)
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#BDC3C7')
    ax.spines['bottom'].set_color('#BDC3C7')

    ax.yaxis.grid(True, linestyle='--', alpha=0.4, color='#95A5A6')
    ax.set_axisbelow(True) 

    plt.xticks(rotation=45, ha='right', fontsize=9, color=TEXT_COLOR)

    for bar in bars:
        yval = bar.get_height()
        if yval > 0:
            ax.text(
                bar.get_x() + bar.get_width()/2, 
                yval + (df['eixo_y'].max() * 0.01), 
                f'{yval:.2f}', 
                ha='center', 
                va='bottom', 
                fontsize=8, 
                fontweight='bold',
                color=TEXT_COLOR
            )

    plt.tight_layout()

    out_path = _output_dir() / f'grafico_tam_{job_id}.png'
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    
    logger.info('[render_grafico_barras_tam] Finalizado: %s', out_path)
    return out_path
import asyncio
import logging
from pathlib import Path
from unittest.mock import AsyncMock, patch

import matplotlib
matplotlib.use('Agg')  
import matplotlib.pyplot as plt
import pandas as pd

from backend.services.criticidade import get_mongo_collection

logger = logging.getLogger(__name__)

def _output_dir() -> Path:
    try:
        path = Path(__file__).resolve().parent.parent.parent / 'output' / 'images'
    except Exception:
        path = Path.cwd() / 'output' / 'images'
        
    path.mkdir(parents=True, exist_ok=True)
    return path

async def render_grafico_barras_tam(job_id: str) -> Path:
    """
    Lê a collection TAM, gera um gráfico de barras:
    X: NOME (ou CTMT se NOME for nulo)
    Y: COMP_KM
    Título: dist_name
    """
    cursor = get_mongo_collection('TAM').find({'job_id': job_id})
    dados = await cursor.to_list(length=1000)

    if not dados:
        raise ValueError(f'Nenhum dado encontrado na collection TAM para o job_id: {job_id}')

    df = pd.DataFrame(dados)
    
    df['eixo_x'] = df['NOME'].fillna(df['CTMT']).fillna("S/N").astype(str)
    df['eixo_y'] = pd.to_numeric(df['COMP_KM'], errors='coerce').fillna(0)
    
    titulo_dist = df['dist_name'].iloc[0] if 'dist_name' in df.columns else 'Relatório de Distâncias'

    n_rows = len(df)
    fig_width = max(12, 0.7 * n_rows) 
    fig, ax = plt.subplots(figsize=(fig_width, 8))

    bars = ax.bar(df['eixo_x'], df['eixo_y'], color='#2196F3', edgecolor='black', alpha=0.8)

    ax.set_title(f'{titulo_dist}', fontsize=16, pad=20, fontweight='bold')
    ax.set_xlabel('Identificação (NOME/CTMT)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Comprimento (KM)', fontsize=12, fontweight='bold')
    
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)
    ax.set_axisbelow(True) 

    plt.xticks(rotation=45, ha='right', fontsize=9)

    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, yval + 0.1, f'{yval:.2f}', 
                ha='center', va='bottom', fontsize=8, fontweight='bold')

    plt.tight_layout()

    out_path = _output_dir() / f'grafico_tam_{job_id}.png'
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    
    logger.info('Gráfico TAM salvo em %s', out_path)
    return out_path

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    TEST_JOB_ID = "job-mock-123"
    
    mock_dados = [
        {'NOME': 'ALIMENTADOR ALFA', 'CTMT': '101', 'COMP_KM': 45.52, 'dist_name': 'ENERGISA_MOCK_DIST'},
        {'NOME': None, 'CTMT': '202', 'COMP_KM': 12.80, 'dist_name': 'ENERGISA_MOCK_DIST'},
        {'NOME': 'ALIMENTADOR GAMA', 'CTMT': '303', 'COMP_KM': 33.15, 'dist_name': 'ENERGISA_MOCK_DIST'},
        {'NOME': 'ALIMENTADOR DELTA', 'CTMT': '404', 'COMP_KM': 65.20, 'dist_name': 'ENERGISA_MOCK_DIST'},
        {'NOME': '', 'CTMT': '505', 'COMP_KM': 8.90, 'dist_name': 'ENERGISA_MOCK_DIST'},
    ]

    async def run_test():
        print(f"🚀 Iniciando teste com Mock de dados para o job_id: {TEST_JOB_ID}...")
 
        with patch("__main__.get_mongo_collection") as mock_get:
            mock_cursor = AsyncMock()
            mock_cursor.to_list.return_value = mock_dados
            mock_get.return_value.find.return_value = mock_cursor
            
            try:
                resultado = await render_grafico_barras_tam(TEST_JOB_ID)
                print(f"Sucesso! Gráfico gerado em: {resultado.absolute()}")
            except Exception as e:
                print(f"Erro ao gerar gráfico: {e}")
                import traceback
                traceback.print_exc()

    asyncio.run(run_test())
import logging
import pickle
from pathlib import Path

import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

_MODEL_DIR = Path(__file__).resolve().parent.parent / 'models'
_PROPHET_FORECASTS_PATH = _MODEL_DIR / 'prophet_forecasts.pkl'
_HIERARCHICAL_AGG_PATH = _MODEL_DIR / 'df_hierarchical_agg.pkl'

_INDICATORS = ['DEC', 'FEC']
_COR_HISTORICO = '#4CAF50'
_COR_PREVISAO = "red"
_ALPHA_IC = 0.2


def _output_dir() -> Path:
    path = Path(__file__).resolve().parent.parent.parent / 'output' / 'images'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_pickle(path: Path):
    with open(path, 'rb') as f:
        return pickle.load(f)


def _render_forecast_chart(
    sig_agente: str,
    indicador: str,
    forecast_df,
    historical_data,
) -> Path:
    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')

    ax.plot(
        historical_data['ds'],
        historical_data['y'],
        label='Histórico',
        color=_COR_HISTORICO,
    )
    ax.plot(
        forecast_df['ds'],
        forecast_df['yhat'],
        label='Previsão',
        color=_COR_PREVISAO,
        linestyle='--',
    )
    ax.fill_between(
        forecast_df['ds'],
        forecast_df['yhat_lower'],
        forecast_df['yhat_upper'],
        color=_COR_PREVISAO,
        alpha=_ALPHA_IC,
        label='Intervalo de Confiança',
    )

    ax.set_xlabel('Data', fontsize=9, color='#555555')
    ax.set_ylabel('VlrIndiceEnviado', fontsize=9, color='#555555')
    ax.legend(fontsize=9, framealpha=0.9, edgecolor='#cccccc')
    ax.grid(True, color='#eeeeee', linewidth=0.8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.xticks(rotation=45)
    plt.tight_layout()

    out_path = _output_dir() / f'prophet_{sig_agente}_{indicador}.png'
    plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)

    return out_path


def render_prophet_forecast(sig_agente: str) -> dict:
    if sig_agente is None:
        logger.warning('[prophet_service] SigAgente não informado, pulando geração de gráficos.')
        return {'sig_agente': None, 'render_paths': {}, 'skipped': _INDICATORS}

    sig_agente = sig_agente.strip()
    try:
        prophet_forecasts = _load_pickle(_PROPHET_FORECASTS_PATH)
        df_hierarchical_agg = _load_pickle(_HIERARCHICAL_AGG_PATH)
    except FileNotFoundError as exc:
        raise RuntimeError(f'Arquivo pickle não encontrado: {exc}') from exc

    agente_data = df_hierarchical_agg[df_hierarchical_agg['SigAgente'].str.strip() == sig_agente]

    if agente_data.empty:
        logger.warning('[prophet_service] SigAgente não encontrado. sig_agente=%s', sig_agente)
        return {'sig_agente': None, 'render_paths': {}, 'skipped': _INDICATORS}

    sig_agente = agente_data['SigAgente'].iloc[0].strip()
    padded_agente_key = sig_agente.ljust(20)

    render_paths: dict[str, str] = {}
    skipped: list[str] = []

    for indicador in _INDICATORS:
        key = (padded_agente_key, indicador)

        if key not in prophet_forecasts:
            logger.warning(
                '[prophet_service] Chave não encontrada. '
                'agente=%s indicador=%s',
                sig_agente,
                indicador,
            )
            skipped.append(indicador)
            continue

        forecast_df = prophet_forecasts[key]
        historical_data = df_hierarchical_agg[
            (df_hierarchical_agg['SigAgente'].str.strip() == sig_agente)
            & (df_hierarchical_agg['SigIndicador'] == indicador)
        ][['AnoMes', 'VlrIndiceEnviado']].rename(
            columns={'AnoMes': 'ds', 'VlrIndiceEnviado': 'y'}
        )

        out_path = _render_forecast_chart(
            sig_agente=sig_agente,
            indicador=indicador,
            forecast_df=forecast_df,
            historical_data=historical_data,
        )

        render_paths[indicador] = str(out_path)
        logger.info(
            '[prophet_service] Gráfico salvo. indicador=%s path=%s',
            indicador,
            out_path,
        )

    return {
        'sig_agente': sig_agente,
        'render_paths': render_paths,
        'skipped': skipped,
    }

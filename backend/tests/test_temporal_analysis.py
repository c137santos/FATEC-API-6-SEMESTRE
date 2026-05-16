from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from backend.services.temporal_analysis import render_prophet_forecast

CNPJ_STR = '2341467000120'
CNPJ_INT = int(CNPJ_STR)
SIG_AGENTE = 'COSERN'
PADDED_AGENTE = SIG_AGENTE.ljust(20)


def _make_df_hierarchical_agg() -> pd.DataFrame:
    rows = []
    for indicador in ['DEC', 'FEC']:
        for mes in pd.date_range('2022-01-01', periods=12, freq='MS'):
            rows.append({
                'NumCNPJ': CNPJ_INT,
                'SigAgente': SIG_AGENTE,
                'SigIndicador': indicador,
                'AnoMes': mes,
                'VlrIndiceEnviado': 1.5,
            })
    return pd.DataFrame(rows)


def _make_forecast_df() -> pd.DataFrame:
    dates = pd.date_range('2022-01-01', periods=24, freq='MS')
    return pd.DataFrame({
        'ds': dates,
        'yhat': [1.0] * 24,
        'yhat_lower': [0.8] * 24,
        'yhat_upper': [1.2] * 24,
    })


def _make_prophet_forecasts() -> dict:
    forecast = _make_forecast_df()
    return {
        (PADDED_AGENTE, 'DEC'): forecast,
        (PADDED_AGENTE, 'FEC'): forecast,
    }


def _patch_pickles(forecasts=None, agg=None):
    if forecasts is None:
        forecasts = _make_prophet_forecasts()
    if agg is None:
        agg = _make_df_hierarchical_agg()

    def fake_load(path):
        if 'prophet_forecasts' in str(path):
            return forecasts
        if 'df_hierarchical_agg' in str(path):
            return agg
        raise FileNotFoundError(path)

    return patch(
        'backend.services.temporal_analysis._load_pickle',
        side_effect=fake_load,
    )


def test_retorna_done_com_dois_indicadores(tmp_path):
    with (
        _patch_pickles(),
        patch(
            'backend.services.temporal_analysis._output_dir',
            return_value=tmp_path,
        ),
    ):
        result = render_prophet_forecast(CNPJ_STR)

    assert result['sig_agente'] == SIG_AGENTE
    assert 'DEC' in result['render_paths']
    assert 'FEC' in result['render_paths']
    assert result['skipped'] == []


def test_salva_arquivos_png(tmp_path):
    with (
        _patch_pickles(),
        patch(
            'backend.services.temporal_analysis._output_dir',
            return_value=tmp_path,
        ),
    ):
        result = render_prophet_forecast(CNPJ_STR)

    for path_str in result['render_paths'].values():
        assert Path(path_str).exists()
        assert path_str.endswith('.png')


def test_cnpj_string_convertido_para_int(tmp_path):
    """Garante que CNPJ recebido como string é comparado corretamente."""
    agg = _make_df_hierarchical_agg()
    agg['NumCNPJ'] = agg['NumCNPJ'].astype('int64')

    with (
        _patch_pickles(agg=agg),
        patch(
            'backend.services.temporal_analysis._output_dir',
            return_value=tmp_path,
        ),
    ):
        result = render_prophet_forecast(CNPJ_STR)

    assert result['sig_agente'] == SIG_AGENTE


def test_cnpj_nao_encontrado_retorna_skipped():
    with _patch_pickles():
        result = render_prophet_forecast('0000000000000')

    assert result['sig_agente'] is None
    assert result['render_paths'] == {}
    assert set(result['skipped']) == {'DEC', 'FEC'}


def test_indicador_sem_chave_vai_para_skipped(tmp_path):
    forecasts = {(PADDED_AGENTE, 'DEC'): _make_forecast_df()}

    with (
        _patch_pickles(forecasts=forecasts),
        patch(
            'backend.services.temporal_analysis._output_dir',
            return_value=tmp_path,
        ),
    ):
        result = render_prophet_forecast(CNPJ_STR)

    assert 'DEC' in result['render_paths']
    assert 'FEC' in result['skipped']


def test_pickle_nao_encontrado_levanta_runtime_error():
    with patch(
        'backend.services.temporal_analysis._load_pickle',
        side_effect=FileNotFoundError('arquivo.pkl'),
    ):
        with pytest.raises(
            RuntimeError, match='Arquivo pickle não encontrado'
        ):
            render_prophet_forecast(CNPJ_STR)


def test_nome_arquivo_contem_agente_e_indicador(tmp_path):
    with (
        _patch_pickles(),
        patch(
            'backend.services.temporal_analysis._output_dir',
            return_value=tmp_path,
        ),
    ):
        result = render_prophet_forecast(CNPJ_STR)

    for indicador, path_str in result['render_paths'].items():
        assert SIG_AGENTE in path_str
        assert indicador in path_str

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.database import get_mongo_sync_db

logger = logging.getLogger(__name__)


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.strip().replace(',', '.')
            if not value:
                return None
        return float(value)
    except (ValueError, TypeError):
        return None


def _calcular_desvio(realizado: float, limite: Optional[float]) -> float:
    if limite and limite > 0:
        return max(0.0, ((realizado - limite) / limite) * 100)
    return 0.0


@dataclass
class _IndicadoresConj:
    dec_realizado: dict
    fec_realizado: dict
    dec_limite: dict
    fec_limite: dict


@dataclass
class _DadosConj:
    soma_comp_m: dict
    qtde_religadores: dict
    nome_por_conj: dict
    indicadores: _IndicadoresConj


def _build_result_item(conj: str, comp_m: float, dados: _DadosConj) -> dict:
    comp_km = comp_m / 1000.0
    qtd_rel = dados.qtde_religadores.get(conj, 0)

    dec_r = dados.indicadores.dec_realizado.get(conj, 0.0)
    fec_r = dados.indicadores.fec_realizado.get(conj, 0.0)
    dec_l = dados.indicadores.dec_limite.get(conj)
    fec_l = dados.indicadores.fec_limite.get(conj)

    desvio_dec = _calcular_desvio(dec_r, dec_l)
    desvio_fec = _calcular_desvio(fec_r, fec_l)

    score_criticidade = desvio_dec + desvio_fec
    divisor = qtd_rel if qtd_rel > 0 else 1
    sam_km = (comp_km * score_criticidade / 100) / divisor

    return {
        'conjunto': conj,
        'nome': dados.nome_por_conj.get(conj, conj),
        'comp_km': round(comp_km, 6),
        'qtde_religadores': qtd_rel,
        'dec_realizado': round(dec_r, 4),
        'fec_realizado': round(fec_r, 4),
        'dec_limite': round(dec_l, 4) if dec_l is not None else None,
        'fec_limite': round(fec_l, 4) if fec_l is not None else None,
        'desvio_dec': round(desvio_dec, 4),
        'desvio_fec': round(desvio_fec, 4),
        'score_criticidade': round(score_criticidade, 4),
        'sam_km': round(sam_km, 6),
    }


def _build_results(dados: _DadosConj) -> List[Dict]:
    resultados = [
        _build_result_item(conj, comp_m, dados)
        for conj, comp_m in dados.soma_comp_m.items()
    ]
    resultados.sort(key=lambda x: x['sam_km'], reverse=True)
    return resultados


def _carregar_comprimentos(db, job_id: str) -> dict:
    soma_comp_m: dict[str, float] = defaultdict(float)
    for row in db.segmentos_mt_tabular.find(
        {'job_id': job_id},
        {'_id': 0, 'CONJ': 1, 'COMP': 1},
    ):
        conj = str(row.get('CONJ', '')).strip()
        comp = _to_float(row.get('COMP'))
        if conj and comp is not None:
            soma_comp_m[conj] += comp
    logger.info(
        '[calculate_sam] Comprimento carregado. job_id=%s conjuntos=%d',
        job_id,
        len(soma_comp_m),
    )
    return soma_comp_m


def _carregar_religadores(db, job_id: str) -> dict:
    religadores_por_conj: dict[str, set] = defaultdict(set)
    for row in db.unsemt.find(
        {'job_id': job_id},
        {'_id': 0, 'conj': 1, 'coordinates': 1},
    ):
        conj = str(row.get('conj', '')).strip()
        coords = row.get('coordinates')
        if conj and coords is not None:
            religadores_por_conj[conj].add(
                tuple(coords) if isinstance(coords, list) else coords
            )
    qtde = {conj: len(coords) for conj, coords in religadores_por_conj.items()}
    logger.info(
        '[calculate_sam] Religadores carregados. job_id=%s conjuntos=%d',
        job_id,
        len(qtde),
    )
    return qtde


def _carregar_indicadores(db, sig_agente: str, ano_indice: int) -> tuple:
    dec_realizado: dict[str, float] = {}
    fec_realizado: dict[str, float] = {}
    for row in db.dec_fec_realizado.find(
        {
            'sig_agente': sig_agente,
            'ano_indice': ano_indice,
            'sig_indicador': {'$in': ['DEC', 'FEC']},
        },
        {'_id': 0, 'ide_conj': 1, 'sig_indicador': 1, 'vlr_indice': 1},
    ):
        ide_conj = str(row.get('ide_conj', '')).strip()
        indicador = row.get('sig_indicador', '')
        vlr = _to_float(row.get('vlr_indice'))
        if not ide_conj or vlr is None:
            continue
        if indicador == 'DEC':
            dec_realizado[ide_conj] = dec_realizado.get(ide_conj, 0.0) + vlr
        elif indicador == 'FEC':
            fec_realizado[ide_conj] = fec_realizado.get(ide_conj, 0.0) + vlr
    logger.info(
        '[calculate_sam] DEC/FEC realizados carregados. '
        'sig_agente=%s ano=%d conjs_dec=%d conjs_fec=%d',
        sig_agente,
        ano_indice,
        len(dec_realizado),
        len(fec_realizado),
    )
    return dec_realizado, fec_realizado


def _carregar_limites(db, sig_agente: str, ano_indice: int) -> tuple:
    dec_limite: dict[str, float] = {}
    fec_limite: dict[str, float] = {}
    for row in db.dec_fec_limite.find(
        {
            'sig_agente': sig_agente,
            'ano_limite': ano_indice,
            'sig_indicador': {'$in': ['DEC', 'FEC']},
        },
        {'_id': 0, 'ide_conj': 1, 'sig_indicador': 1, 'vlr_limite': 1},
    ):
        ide_conj = str(row.get('ide_conj', '')).strip()
        indicador = row.get('sig_indicador', '')
        vlr = _to_float(row.get('vlr_limite'))
        if not ide_conj or vlr is None:
            continue
        if indicador == 'DEC':
            dec_limite[ide_conj] = vlr
        elif indicador == 'FEC':
            fec_limite[ide_conj] = vlr
    logger.info(
        '[calculate_sam] Limites carregados. '
        'sig_agente=%s ano=%d conjs_dec=%d conjs_fec=%d',
        sig_agente,
        ano_indice,
        len(dec_limite),
        len(fec_limite),
    )
    return dec_limite, fec_limite


def _carregar_nomes(db, job_id: str) -> dict:
    nome_por_conj: dict[str, str] = {}
    doc_conj = db.conjuntos.find_one({'job_id': job_id})
    if doc_conj and 'records' in doc_conj:
        for r in doc_conj['records']:
            cod = str(r.get('cod_id', '')).strip()
            nome = str(r.get('nome', '')).strip()
            if cod:
                nome_por_conj[cod] = nome or cod
    logger.info(
        '[calculate_sam] Nomes carregados. job_id=%s conjuntos=%d',
        job_id,
        len(nome_por_conj),
    )
    return nome_por_conj


def calculate_sam(
    job_id: str,
    distribuidora_id: str,
    sig_agente: str,
    ano_indice: int,
) -> List[Dict]:
    logger.info(
        '[calculate_sam] Iniciando cálculo. '
        'distribuidora_id=%s job_id=%s sig_agente=%s ano=%d',
        distribuidora_id,
        job_id,
        sig_agente,
        ano_indice,
    )
    db = get_mongo_sync_db()

    dec_realizado, fec_realizado = _carregar_indicadores(
        db, sig_agente, ano_indice
    )
    dec_limite, fec_limite = _carregar_limites(db, sig_agente, ano_indice)

    dados = _DadosConj(
        soma_comp_m=_carregar_comprimentos(db, job_id),
        qtde_religadores=_carregar_religadores(db, job_id),
        nome_por_conj=_carregar_nomes(db, job_id),
        indicadores=_IndicadoresConj(
            dec_realizado=dec_realizado,
            fec_realizado=fec_realizado,
            dec_limite=dec_limite,
            fec_limite=fec_limite,
        ),
    )

    results = _build_results(dados)

    logger.info(
        '[calculate_sam] Cálculo concluído. job_id=%s conjuntos=%d',
        job_id,
        len(results),
    )

    salvar_sam(
        distribuidora_id=distribuidora_id,
        job_id=job_id,
        sig_agente=sig_agente,
        ano_indice=ano_indice,
        records=results,
    )
    return results


def salvar_sam(
    distribuidora_id: str,
    job_id: str,
    sig_agente: str,
    ano_indice: int,
    records: List[Dict],
) -> None:
    try:
        db = get_mongo_sync_db()
        db['sam_resultados'].insert_one({
            'distribuidora_id': distribuidora_id,
            'job_id': job_id,
            'sig_agente': sig_agente,
            'ano_indice': ano_indice,
            'processed_at': datetime.now(tz=timezone.utc),
            'records': records,
        })
        logger.info(
            '[calculate_sam] Resultados salvos. '
            'distribuidora_id=%s job_id=%s conjuntos=%d',
            distribuidora_id,
            job_id,
            len(records),
        )
    except Exception:
        logger.error('[calculate_sam] Erro ao salvar resultados.')
        raise

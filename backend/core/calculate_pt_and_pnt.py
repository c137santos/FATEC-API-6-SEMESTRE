import logging
from collections import defaultdict

from pymongo import MongoClient

from backend.settings import Settings

logger = logging.getLogger(__name__)


PT_COLUMNS = [
    'PERD_A3a',
    'PERD_A4',
    'PERD_B',
    'PERD_MED',
    'PERD_A3a_B',
    'PERD_A4_B',
    'PERD_B_A3a',
    'PERD_B_A4',
    'PERD_A3aA4',
    'PERD_A4A3a',
]

PNT_COLUMNS = [
    *[f'PNTMT_{i:02d}' for i in range(1, 13)],
    *[f'PNTBT_{i:02d}' for i in range(1, 13)],
]

ENE_COLUMNS = [f'ENE_{i:02d}' for i in range(1, 13)]


def _to_float(value) -> float:
    if value is None:
        return 0.0
    try:
        if isinstance(value, str):
            value = value.strip().replace(',', '.')
            if not value:
                return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _sum_columns(record: dict, colunas: list[str]) -> float:
    return sum(_to_float(record.get(col)) for col in colunas)


def calculate_pt_pnt(job_id: str) -> list[dict]:
    settings = Settings()
    client = MongoClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB]

    logger.info('[pt_pnt] Iniciando cálculo. job_id=%s', job_id)

    doc_ctmt = db['circuitos_mt'].find_one({'job_id': job_id})
    if not doc_ctmt:
        logger.warning('[pt_pnt] Nenhum dado CTMT para job_id=%s', job_id)
        return []

    ctmt_by_cod: dict[str, dict] = {
        r['COD_ID']: r for r in doc_ctmt.get('records', []) if r.get('COD_ID')
    }
    logger.info('[pt_pnt] CTMT carregado. circuitos=%d', len(ctmt_by_cod))

    doc_conj = db['conjuntos'].find_one({'job_id': job_id})
    if not doc_conj:
        logger.warning('[pt_pnt] Nenhum dado CONJ para job_id=%s', job_id)
        return []

    name_by_conj: dict[str, str] = {
        r['cod_id']: r.get('nome', r['cod_id'])
        for r in doc_conj.get('records', [])
        if r.get('cod_id')
    }
    logger.info('[pt_pnt] CONJ carregado. conjuntos=%d', len(name_by_conj))

    ctmt_to_conjs: dict[str, set[str]] = defaultdict(set)
    cursor = db['segmentos_mt_tabular'].find(
        {'job_id': job_id},
        {'CTMT': 1, 'CONJ': 1, '_id': 0},
    )
    for seg in cursor:
        ctmt_cod = seg.get('CTMT')
        conj_cod = seg.get('CONJ')
        if ctmt_cod and conj_cod:
            ctmt_to_conjs[ctmt_cod].add(conj_cod)

    logger.info(
        '[pt_pnt] SSDMT carregado. pares_ctmt_conj=%d', len(ctmt_to_conjs)
    )

    accumulated: dict[str, dict[str, float]] = defaultdict(
        lambda: {'pt': 0.0, 'pnt': 0.0, 'ene': 0.0}
    )

    for ctmt_cod, conjs in ctmt_to_conjs.items():
        record = ctmt_by_cod.get(ctmt_cod)
        if not record:
            continue
        pt = _sum_columns(record, PT_COLUMNS)
        pnt = _sum_columns(record, PNT_COLUMNS)
        ene = _sum_columns(record, ENE_COLUMNS)
        for conj_cod in conjs:
            accumulated[conj_cod]['pt'] += pt
            accumulated[conj_cod]['pnt'] += pnt
            accumulated[conj_cod]['ene'] += ene

    results = []
    for conj_cod, vals in accumulated.items():
        pt_mwh = vals['pt'] / 1000
        pnt_mwh = vals['pnt'] / 1000
        ene_mwh = vals['ene'] / 1000
        total_pt_and_pnt = pt_mwh + pnt_mwh

        pct_pt = (
            (pt_mwh / total_pt_and_pnt * 100) if total_pt_and_pnt else None
        )
        pct_pnt = (
            (pnt_mwh / total_pt_and_pnt * 100) if total_pt_and_pnt else None
        )

        results.append({
            'conjunto': name_by_conj.get(conj_cod, conj_cod),
            'pt_mwh': round(pt_mwh, 4),
            'pnt_mwh': round(pnt_mwh, 4),
            'energia_injetada_mwh': round(ene_mwh, 4),
            'pct_pt': round(pct_pt, 4) if pct_pt is not None else None,
            'pct_pnt': round(pct_pnt, 4) if pct_pnt is not None else None,
        })

    results.sort(key=lambda x: x['pnt_mwh'], reverse=True)

    logger.info('[pt_pnt] Cálculo concluído. conjuntos=%d', len(results))
    return results

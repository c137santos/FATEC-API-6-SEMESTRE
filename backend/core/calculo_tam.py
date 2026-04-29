from collections import defaultdict
from typing import Any, Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def _to_float(value: Any) -> Optional[float]:
    """Converte valor para float de forma segura."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


async def calculo_tam(
    db, job_id: str
) -> Tuple[List[dict], List[dict], List[dict]]:
    """
    Constrói as tabelas TAM (Trechos, Ranking por Conjunto, Top 10)
    usando dados reais do MongoDB, simulando o JOIN do pandas/geopandas.
    """

    ssdmt_cursor = db.segmentos_mt_tabular.find(
        {'job_id': job_id},
        {'_id': 0, 'COD_ID': 1, 'DIST': 1, 'CTMT': 1, 'CONJ': 1, 'COMP': 1},
    )

    ctmt_doc = await db.circuitos_mt.find_one(
        {'job_id': job_id}, {'_id': 0, 'records.COD_ID': 1, 'records.NOME': 1}
    )

    mapping_cod_id_to_nome: Dict[str, str] = {}

    if ctmt_doc and 'records' in ctmt_doc:
        for record in ctmt_doc.get('records', []):
            cod_id = record.get('COD_ID')
            nome = record.get('NOME')

            if cod_id is not None:
                cod_id_str = str(cod_id).strip()
                nome_str = str(nome).strip() if nome is not None else ''

                if nome_str != '' and cod_id_str not in mapping_cod_id_to_nome:
                    mapping_cod_id_to_nome[cod_id_str] = nome_str
    else:
        ctmt_cursor = db.circuitos_mt.find(
            {'job_id': job_id}, {'_id': 0, 'COD_ID': 1, 'NOME': 1}
        )

        async for ctmt in ctmt_cursor:
            cod_id = ctmt.get('COD_ID')
            nome = ctmt.get('NOME')

            if cod_id is not None:
                cod_id_str = str(cod_id).strip()
                nome_str = str(nome).strip() if nome is not None else ''

                if nome_str != '' and cod_id_str not in mapping_cod_id_to_nome:
                    mapping_cod_id_to_nome[cod_id_str] = nome_str

    sample_items = list(mapping_cod_id_to_nome.items())[:5]
    for cod_id, nome in sample_items:
        logger.debug(f'  Mapeamento: {cod_id} -> {nome}')

    soma_por_trecho: Dict[Tuple, float] = defaultdict(float)

    async for row in ssdmt_cursor:
        cod_id = row.get('COD_ID')
        dist = row.get('DIST')
        conj = row.get('CONJ')
        ctmt = row.get('CTMT')
        comp_raw = row.get('COMP')

        comp = _to_float(comp_raw)
        if comp is None:
            continue

        ctmt_str = str(ctmt).strip() if ctmt is not None else ''

        nome = mapping_cod_id_to_nome.get(ctmt_str)

        if nome is None:
            nome = ctmt_str if ctmt_str else 'SEM_NOME'

        comp_km = comp / 1000.0

        key = (dist, conj, ctmt, nome)

        soma_por_trecho[key] += comp_km

    calculo_trechos = [
        {
            'DIST': dist,
            'CONJ': conj,
            'CTMT': ctmt,
            'NOME': nome,
            'COMP_KM': comp_km,
        }
        for (dist, conj, ctmt, nome), comp_km in soma_por_trecho.items()
    ]

    calculo_trechos.sort(key=lambda x: (x['DIST'], x['CONJ'], x['CTMT']))

    soma_por_conjunto: Dict[Tuple, float] = defaultdict(float)

    for trecho in calculo_trechos:
        key = (trecho['CONJ'], trecho['NOME'])
        soma_por_conjunto[key] += trecho['COMP_KM']

    ranking_por_conjunto = [
        {'CONJ': conj, 'NOME': nome, 'COMP_KM': round(comp_km, 6)}
        for (conj, nome), comp_km in soma_por_conjunto.items()
    ]

    ranking_por_conjunto.sort(key=lambda x: x['COMP_KM'], reverse=True)

    ranking_top_10_conjunto = ranking_por_conjunto[:10]

    return calculo_trechos, ranking_por_conjunto, ranking_top_10_conjunto

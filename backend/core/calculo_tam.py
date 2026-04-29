from datetime import datetime
from collections import defaultdict
from typing import Any, Dict, List, Tuple, Optional
import logging
import asyncpg
from settings import Settings

logger = logging.getLogger(__name__)
settings = Settings()


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

async def calculo_tam(db, job_id: str, pg_db: asyncpg.Connection) -> Tuple[List[dict], List[dict], List[dict]]:
    """
    Realiza o cálculo do TAM cruzando dados do MongoDB com metadados originários do Postgres.
    """

    try:
        row = await pg_db.fetchrow(
            "SELECT id, date_gdb, dist_name FROM distribuidoras WHERE job_id = $1", 
            job_id
        )
        if not row:
            logger.error(f"Job {job_id} não encontrado no PostgreSQL.")
            raise ValueError(f"Job {job_id} não encontrado.")
            
        info_pg = {
            "id": row['id'], 
            "ano": row['date_gdb'], 
            "nome": row['dist_name']
        }
    except Exception as e:
        logger.error(f"Erro ao buscar metadados no Postgres: {e}")
        raise 

    data_processamento = datetime.now()

    mapping_ctmt_nome: Dict[str, str] = {}
    ctmt_cursor = db.circuitos_mt.find({'job_id': job_id}, {'_id': 0, 'COD_ID': 1, 'NOME': 1})
    
    async for ctmt_doc in ctmt_cursor:
        cod_id = ctmt_doc.get('COD_ID')
        nome_circ = ctmt_doc.get('NOME')
        if cod_id:
            mapping_ctmt_nome[str(cod_id).strip()] = str(nome_circ).strip()

    ssdmt_cursor = db.segmentos_mt_tabular.find(
        {'job_id': job_id},
        {'_id': 0, 'DIST': 1, 'CTMT': 1, 'CONJ': 1, 'COMP': 1},
    )

    soma_por_trecho = defaultdict(float)
    async for row in ssdmt_cursor:
        comp = _to_float(row.get('COMP'))
        if comp is None: 
            continue

        dist_linha = row.get('DIST') 
        conj = row.get('CONJ')
        ctmt_key = str(row.get('CTMT', '')).strip()
        nome_circuito = mapping_ctmt_nome.get(ctmt_key, ctmt_key if ctmt_key else 'SEM_NOME')
        
        chave = (dist_linha, conj, ctmt_key, nome_circuito)
        soma_por_trecho[chave] += (comp / 1000.0)

    documentos_para_salvar = []

    for (dist, conj, ctmt, nome), comp_km in soma_por_trecho.items():
        documentos_para_salvar.append({
            'job_id': job_id,
            'id': info_pg["id"],          
            'dist_name': info_pg["nome"],    
            'ano_gdb': info_pg["ano"],       
            'data_processamento': data_processamento,
            'DIST': dist, 
            'CONJ': conj,
            'CTMT': ctmt,
            'NOME': nome,
            'COMP_KM': round(comp_km, 6)
        })

    if documentos_para_salvar:
        await db.TAM.delete_many({'job_id': job_id})
        await db.TAM.insert_many(documentos_para_salvar)
        for doc in documentos_para_salvar:
            if '_id' in doc: 
                doc['_id'] = str(doc['_id'])

    calculo_trechos = sorted(documentos_para_salvar, key=lambda x: (str(x.get('DIST')), str(x.get('CONJ')), str(x.get('CTMT'))))

    soma_conjunto: Dict[Tuple, float] = defaultdict(float)
    for d in documentos_para_salvar:
        soma_conjunto[(d['CONJ'], d['NOME'])] += d['COMP_KM']

    ranking_conjunto = [
        {
            'CONJ': c, 
            'NOME': n, 
            'COMP_KM': round(v, 6),
            'id': info_pg.get('id'),
            'dist_name': info_pg.get('nome')
        } 
        for (c, n), v in soma_conjunto.items()
    ]
    ranking_conjunto.sort(key=lambda x: x['COMP_KM'], reverse=True)

    return calculo_trechos, ranking_conjunto, ranking_conjunto[:10]
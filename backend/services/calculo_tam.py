import logging
from datetime import datetime
from collections import defaultdict
from typing import Any, Dict, List, Optional

from backend.core.schemas import TamResponse, DistributorMetadata
from backend.database import get_mongo_async_db, get_mongo_sync_db

logger = logging.getLogger(__name__)

def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (ValueError, TypeError):
        return None
    

async def obter_resultados_tam(job_id: str) -> List[Dict]:
    """
    Busca os resultados processados no MongoDB.
    Utiliza o singleton async para não travar a aplicação.
    """
    db = get_mongo_async_db()
    cursor = db.TAM.find({"job_id": job_id}, {"_id": 0})
    return await cursor.to_list(length=None)


def calcular_extensao_tam(
    metadata: DistributorMetadata,   
    segmentos: List[dict],
    map_circuitos: Dict[str, str],
    map_conjuntos: Dict[str, str]
) -> List[TamResponse]:
    
    data_proc = datetime.now().isoformat()
    soma_por_trecho = defaultdict(float)

    for row in segmentos:
        comp = _to_float(row.get('COMP'))
        if comp is None: 
            continue

        c_conj = str(row.get('CONJ', '')).strip()
        c_ctmt = str(row.get('CTMT', '')).strip()
        
        n_conj = map_conjuntos.get(c_conj, c_conj)
        n_circ = map_circuitos.get(c_ctmt, c_ctmt)

        chave = (c_conj, n_conj, c_ctmt, n_circ)
        soma_por_trecho[chave] += (comp / 1000.0)

    return [
        TamResponse(
            job_id=metadata.job_id,
            id_dist=metadata.id,
            dist_name=metadata.dist_name, 
            ano_gdb=metadata.date_gdb,
            data_processamento=data_proc,
            CONJ=n_conj_val,
            CTMT=c_ctmt_val,
            NOME=n_circ_val,
            COMP_KM=round(km, 6)
        )
        for (c_conj_val, n_conj_val, c_ctmt_val, n_circ_val), km in soma_por_trecho.items()
    ]


async def ranking_tam(
    resultados: list[TamResponse], 
    top_n: int = 10
) -> list[TamResponse]:
    
    """
    Recebe a lista de objetos TamResponse e retorna o ranking ordenado
    do maior para o menor COMP_KM.
    """
    ranking_completo = sorted(
        resultados, 
        key=lambda x: x.COMP_KM, 
        reverse=True
    )

    return ranking_completo[:top_n]

    
def salvar_resultados_tam(trechos: List[TamResponse]):
    """Versão síncrona para ser usada por tasks Celery."""
    if not trechos:
        return False
        
    try:
        db = get_mongo_sync_db()
        job_id = trechos[0].job_id
        
        documentos = [t.model_dump() for t in trechos]
        
        db.TAM.delete_many({"job_id": job_id})
        db.TAM.insert_many(documentos)
        
        logger.info(f"TAM persistido (sync) para o job {job_id}")
        return True
        
    except Exception as e:
        logger.error(f"Falha na persistência sync do TAM: {e}")
        raise

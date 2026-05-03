import logging
from datetime import datetime
from typing import Dict, List

from backend.core.schemas import TamResponse, DistributorMetadata
from backend.database import get_mongo_async_db, get_mongo_sync_db

logger = logging.getLogger(__name__)
    

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
    resultados = []

    for row in segmentos:
        c_conj = str(row.get('conjunto', '')).strip()
        c_ctmt = str(row.get('circuito', '')).strip()
        extensao_bruta = row.get('extensao', 0.0) 

        n_conj = map_conjuntos.get(c_conj, c_conj)
        n_circ = map_circuitos.get(c_ctmt, c_ctmt)

        km = extensao_bruta / 1000.0

        resultados.append(
            TamResponse(
                job_id=metadata.job_id,
                id_dist=metadata.id,
                dist_name=metadata.dist_name, 
                ano_gdb=metadata.date_gdb,
                data_processamento=data_proc,
                CONJ=n_conj,
                CTMT=c_ctmt,
                NOME=n_circ,
                COMP_KM=round(km, 6)
            )
        )

    return resultados


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

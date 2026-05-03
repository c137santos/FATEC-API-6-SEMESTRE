import logging
from datetime import datetime

from backend.database import get_mongo_sync_db
from backend.services.calculo_tam import calcular_extensao_tam, salvar_resultados_tam
from backend.tasks.celery_app import celery_app
from backend.core.schemas import DistributorMetadata

logger = logging.getLogger(__name__)


@celery_app.task(
        name='etl.calcular_tam',
        bind=True,
        max_retries=5,
        default_retry_delay=60
    )
def task_calcular_tam(self, job_id: str, metadados_dist: dict):
    db = get_mongo_sync_db()

    pipeline = [
        {"$match": {"job_id": job_id}},
        {
            "$group": {
                "_id": {
                    "CONJ": "$CONJ",
                    "CTMT": "$CTMT"
                },
                "extensao_total": {"$sum": "$COMP"},
                "quantidade_segmentos": {"$sum": 1}
            }
        },
        {
            "$project": {
                "_id": 0,
                "conjunto": "$_id.CONJ",
                "circuito": "$_id.CTMT",
                "extensao": "$extensao_total",
                "contagem": "$quantidade_segmentos"
            }
        }
    ]

    segmentos = list(db.segmentos_mt_tabular.aggregate(pipeline))
    
    if not segmentos:
        logger.warning(f"Dados ainda não disponíveis para o job {job_id}. Tentando novamente...")
        raise self.retry(exc=RuntimeError(f"Segmentos não encontrados para o job {job_id}"))
    
    try:
        metadata = DistributorMetadata(**metadados_dist, job_id=job_id)

        resultados = calcular_extensao_tam(
            metadata=metadata,
            segmentos=segmentos,
            map_circuitos={}, 
            map_conjuntos={}
        )
        
        salvar_resultados_tam(resultados)
        
        db.TAM_status.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "completed", 
                "finished_at": datetime.now()
            }},
            upsert=True 
        )
        
        return {"job_id": job_id, "status": "success"}
    
    except Exception as e:
        logger.error(f"Erro ao calcular TAM para o job {job_id}: {e}")
        raise self.retry(exc=e, max_retries=2)
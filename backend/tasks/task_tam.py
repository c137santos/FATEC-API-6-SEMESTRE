import logging
from datetime import datetime

from backend.database import get_mongo_sync_db
from backend.services.calculo_tam import calcular_extensao_tam, salvar_resultados_tam
from backend.tasks.celery_app import celery_app
from core.schemas import DistributorMetadata

logger = logging.getLogger(__name__)


@celery_app.task(name='etl.calcular_tam')
def task_calcular_tam(job_id: str, metadados_dist: dict):
    db = get_mongo_sync_db()

    segmentos = list(db.segmentos_mt_tabular.find({"job_id": job_id}))
    
    if not segmentos:
        logger.warning(f"Nenhum dado encontrado para o job {job_id}")
        return
    
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
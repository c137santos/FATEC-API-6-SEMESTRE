from backend.tasks.celery_app import celery_app
from backend.services.calculo_tam import calcular_extensao_tam, salvar_resultados_tam
from backend.database import get_mongo_sync_db


@celery_app.task(name='etl.calcular_tam')
def task_calcular_tam(job_id: str, segmentos: list, metadados_dist: dict):
    """
    Task dedicada ao cálculo de extensão, executada após a extração dos dados.
    """
    
    from core.schemas import DistributorMetadata
    metadata = DistributorMetadata(**metadados_dist, job_id=job_id)

    resultados = calcular_extensao_tam(
        metadata=metadata,
        segmentos=segmentos,
        map_circuitos={}, 
        map_conjuntos={}
    )
    
    db = get_mongo_sync_db() 
    success = salvar_resultados_tam(resultados, db)
    
    return {"job_id": job_id, "status": "tam_calculated", "count": len(resultados)}
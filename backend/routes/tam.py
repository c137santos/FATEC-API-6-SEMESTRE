import logging
from fastapi import APIRouter, Depends, HTTPException

from backend.core.calculo_tam import calculo_tam
from backend.database import get_mongo_async_database

logger = logging.getLogger(__name__)

router = APIRouter()
settings = Settings()


@router.get('/tam/{job_id}')
async def get_json_tam(job_id: str, db=Depends(get_mongo_async_database)):

    try:
        trechos, ranking, top10 = await calculo_tam(mongo_db, job_id, pg_db)
        return {
            "status": "success",
            "metadata": {
                "job_id": job_id,
                "distribuidora_info": ranking[0] if ranking else {}
            },
            "data": {
                "trechos": trechos,
                "ranking_por_conjunto": ranking,
                "top_10": top10
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
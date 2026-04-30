from fastapi import APIRouter, Depends, HTTPException
from backend.database import get_mongo_async_database  

router = APIRouter()

@router.get("/tam/{job_id}")
async def get_tam_results(
    job_id: str,
    mongo_db = Depends(get_mongo_async_database)
):
    """
    Este endpoint não calcula nada. Ele apenas consome o que a 
    Pipeline (Task Celery) já processou e persistiu.
    """
    
    cursor = mongo_db.TAM.find({"job_id": job_id})
    trechos = await cursor.to_list(length=1000)

    if not trechos:
        raise HTTPException(status_code=404, detail="Resultados não encontrados.")

    for trecho in trechos:
        trecho["_id"] = str(trecho["_id"])

    trechos_ordenados = sorted(trechos, key=lambda x: x['COMP_KM'], reverse=True)

    return {
        "status": "success",
        "job_id": job_id,
        "data": {
            "total_registros": len(trechos_ordenados),
            "top_10": trechos_ordenados[:10],
            "todos_trechos": trechos_ordenados
        }
    }
from fastapi import APIRouter, Depends, HTTPException
import os
from pymongo import MongoClient
from ..core.calculo_tam import calculo_tam

# 4d6eefb1-a550-4371-b059-17b1157a6375
# 802e323f-3a26-4473-bb78-ba843a5dab88

router = APIRouter()

def get_db():
    mongo_uri = os.getenv('MONGO_URI', "mongodb://mongodb:27017")
    client = MongoClient(mongo_uri)
    try:
        yield client['fatec_api']
    finally:
        client.close()

@router.get('/tam/{job_id}')
async def get_json_tam(job_id: str, db=Depends(get_db)):

    try:

        calculo_trechos, ranking_conjunto, top_10_conjunto = calculo_tam(db, job_id) 

        return {
            "status": "success",
            "metadata": {
                "job_id": job_id,
            },
            "data": {
                "trechos": calculo_trechos,
                "ranking_por_conjunto": ranking_conjunto,
                "top_10": top_10_conjunto
            }
        }
    
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Erro interno ao processar TAM: {str(e)}')

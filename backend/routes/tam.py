from fastapi import APIRouter, Depends, HTTPException
import os
from motor.motor_asyncio import AsyncIOMotorClient
from ..core.calculo_tam import calculo_tam


router = APIRouter()


async def get_db():

    uri = os.getenv('MONGO_URI')
    db_name = os.getenv('MONGO_DB')

    if not uri:
        raise HTTPException(
            status_code=500, detail='Configuração ausente: MONGO_URI'
        )
    if not db_name:
        raise HTTPException(
            status_code=500, detail='Configuração ausente: MONGO_DB'
        )

    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)

    try:
        yield client[db_name]
    finally:
        client.close()


@router.get('/tam/{job_id}')
async def get_json_tam(job_id: str, db=Depends(get_db)):

    try:
        calculo_trechos, ranking_conjunto, top_10_conjunto = await calculo_tam(
            db, job_id
        )

        if not calculo_trechos:
            raise ValueError('Job inexistente ou sem dados')

        return {
            'status': 'success',
            'metadata': {
                'job_id': job_id,
            },
            'data': {
                'trechos': calculo_trechos,
                'ranking_por_conjunto': ranking_conjunto,
                'top_10': top_10_conjunto,
            },
        }

    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f'Erro interno ao processar TAM: {str(e)}'
        )

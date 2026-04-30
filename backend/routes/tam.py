from fastapi import APIRouter, Depends, HTTPException

from backend.core.calculo_tam import calculo_tam
from backend.database import get_mongo_async_database


router = APIRouter()


@router.get('/tam/{job_id}')
async def get_json_tam(job_id: str, db=Depends(get_mongo_async_database)):

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

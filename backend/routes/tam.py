from typing import List

from fastapi import APIRouter, HTTPException
from backend.services.calculo_tam import obter_resultados_tam
from backend.core.schemas import TamResponse

router = APIRouter()

@router.get(
    "/tam/{job_id}",
    response_model=List[TamResponse],
    status_code=200
)
async def get_tam_results(job_id: str):
    resultados = await obter_resultados_tam(job_id)

    if not resultados:
        raise HTTPException(
            status_code=404, 
            detail="Resultados não encontrados para o job informado."
        )

    return resultados
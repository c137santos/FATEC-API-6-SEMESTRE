from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from backend.core.calculate_pt_and_pnt import calculate_pt_pnt


router = APIRouter()


@router.get(
    '/pt-pnt',
    summary='Perdas Técnicas e Não Técnicas por conjunto elétrico',
)
def get_pt_pnt(job_id: str):
    try:
        results = calculate_pt_pnt(job_id)
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e)
        )

    if not results:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Nenhum dado encontrado para job_id={job_id!r}. '
            'Verifique se o pipeline ETL foi executado com esse job_id.',
        )

    return {
        'job_id': job_id,
        'total_conjuntos': len(results),
        'resultados': results,
    }

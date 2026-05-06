import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from backend.core.schemas import CriticidadeResponse
from backend.services.criticidade import calcular_score_criticidade

logger = logging.getLogger(__name__)

router = APIRouter()

_ANO_MIN = 2015
_ANO_MAX = date.today().year
_DIST_MIN_LEN = 2


@router.get('/criticidade', response_model=CriticidadeResponse)
async def calcular_criticidade_endpoint(
    ano: int = Query(..., description='Ano de análise'),
    distribuidora: str = Query(..., description='Nome da distribuidora'),
) -> CriticidadeResponse:
    """
    Calcula o score de criticidade para uma distribuidora e ano específicos.

    Args:
        ano: Ano de análise (ex: 2024)
        distribuidora: Nome da distribuidora (ex: EQUATORIAL)

    Returns:
        Score de criticidade calculado com desvios DEC e FEC

    Raises:
        HTTPException: Se não houver dados para os parâmetros fornecidos
    """
    try:
        if ano < _ANO_MIN or ano > _ANO_MAX:
            raise HTTPException(
                status_code=400,
                detail=f'Ano deve estar entre {_ANO_MIN} e {_ANO_MAX}',
            )

        if not distribuidora or len(distribuidora.strip()) < _DIST_MIN_LEN:
            raise HTTPException(
                status_code=400,
                detail='Nome da distribuidora deve ter pelo menos 2 caracteres',
            )

        resultado = await calcular_score_criticidade(
            ano, distribuidora.strip()
        )

        if resultado is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f'Dados não encontrados para distribuidora'
                    f" '{distribuidora}' no ano {ano}"
                ),
            )

        logger.info(
            'Score retornado: %.2f para %s em %s',
            resultado['score_criticidade'],
            distribuidora,
            ano,
        )

        return CriticidadeResponse(
            ano=resultado['ano'],
            distribuidora=resultado['distribuidora'],
            score_criticidade=round(resultado['score_criticidade'], 2),
            desvio_dec=round(resultado['desvio_dec'], 2),
            desvio_fec=round(resultado['desvio_fec'], 2),
            cor=resultado['cor'],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error('Erro no endpoint de criticidade: %s', e)
        raise HTTPException(
            status_code=500,
            detail='Erro interno ao processar solicitação',
        )

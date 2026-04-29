import logging

from fastapi import APIRouter, HTTPException, Query

from backend.core.schemas import CriticidadeResponse
from backend.services.criticidade import calcular_score_criticidade

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get('/criticidade', response_model=CriticidadeResponse)
async def calcular_criticidade_endpoint(
    ano: int = Query(..., description='Ano de análise'),
    distribuidora: str = Query(..., description='Nome da distribuidora'),
):
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
        # Validar parâmetros
        if ano < 2000 or ano > 2030:
            raise HTTPException(
                status_code=400, detail='Ano deve estar entre 2000 e 2030'
            )

        if not distribuidora or len(distribuidora.strip()) < 2:
            raise HTTPException(
                status_code=400,
                detail='Nome da distribuidora deve ter pelo menos 2 caracteres',
            )

        # Calcular score de criticidade
        resultado = await calcular_score_criticidade(ano, distribuidora.strip())

        if resultado is None:
            raise HTTPException(
                status_code=404,
                detail=f"Dados não encontrados para distribuidora '{distribuidora}' no ano {ano}",
            )

        logger.info(
            f'Score retornado: {resultado["score_criticidade"]:.2f} para {distribuidora} em {ano}'
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
        logger.error(f'Erro no endpoint de criticidade: {e}')
        raise HTTPException(
            status_code=500, detail='Erro interno ao processar solicitação'
        )

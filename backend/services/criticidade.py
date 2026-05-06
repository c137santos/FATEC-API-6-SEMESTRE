import logging
from typing import Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorCollection

from backend.database import get_mongo_async_db

logger = logging.getLogger(__name__)


def get_mongo_collection(collection_name: str) -> AsyncIOMotorCollection:
    """Obtém uma coleção do MongoDB."""
    return get_mongo_async_db()[collection_name]


def calcular_desvio(realizado: float, limite: float) -> float:
    """Calcula o desvio percentual, com mínimo de 0."""
    if limite == 0:
        return 0.0
    desvio = ((realizado - limite) / limite) * 100
    return max(0.0, desvio)


def classificar_criticidade(score: float) -> str:
    """Classifica a criticidade baseada no score."""
    if score == 0:
        return 'Verde'
    elif 0 < score <= 10:
        return 'Laranja'
    else:
        return 'Vermelho'


async def buscar_dados_realizados(ano: int, distribuidora: str) -> List[Dict]:
    """Busca dados realizados de DEC/FEC para um ano e distribuidora."""
    collection = get_mongo_collection('dec_fec_realizado')

    pipeline = [
        {
            '$match': {
                'ano_indice': ano,
                'sig_agente': distribuidora.upper(),
                'sig_indicador': {'$in': ['DEC', 'FEC']},
            }
        },
        {
            '$group': {
                '_id': {
                    'sig_agente': '$sig_agente',
                    'ide_conj': '$ide_conj',
                    'dsc_conj': '$dsc_conj',
                    'sig_indicador': '$sig_indicador',
                },
                'valor_realizado': {'$sum': '$vlr_indice'},
            }
        },
        {
            '$project': {
                '_id': 0,
                'sig_agente': '$_id.sig_agente',
                'ide_conj': '$_id.ide_conj',
                'dsc_conj': '$_id.dsc_conj',
                'sig_indicador': '$_id.sig_indicador',
                'valor_realizado': 1,
            }
        },
    ]

    resultados = await collection.aggregate(pipeline).to_list(None)
    logger.info(
        'Encontrados %s registros realizados para %s em %s',
        len(resultados),
        distribuidora,
        ano,
    )
    return resultados


async def buscar_dados_limites(ano: int, distribuidora: str) -> List[Dict]:
    """Busca dados limites de DEC/FEC para um ano e distribuidora."""
    collection = get_mongo_collection('dec_fec_limite')

    pipeline = [
        {
            '$match': {
                'ano_limite': ano,
                'sig_agente': distribuidora.upper(),
                'sig_indicador': {'$in': ['DEC', 'FEC']},
            }
        },
        {
            '$project': {
                '_id': 0,
                'sig_agente': '$sig_agente',
                'ide_conj': '$ide_conj',
                'dsc_conj': '$dsc_conj',
                'sig_indicador': '$sig_indicador',
                'valor_limite': '$vlr_limite',
            }
        },
    ]

    resultados = await collection.aggregate(pipeline).to_list(None)
    logger.info(
        'Encontrados %s registros limites para %s em %s',
        len(resultados),
        distribuidora,
        ano,
    )
    return resultados


async def calcular_score_criticidade(
    ano: int, distribuidora: str
) -> Optional[Dict]:
    """
    Calcula o score de criticidade para uma distribuidora e ano específicos.

    Args:
        ano: Ano de análise
        distribuidora: Nome da distribuidora

    Returns:
        Dicionário com o score calculado ou None se não houver dados
    """
    try:
        dados_realizados = await buscar_dados_realizados(ano, distribuidora)
        dados_limites = await buscar_dados_limites(ano, distribuidora)

        if not dados_realizados or not dados_limites:
            logger.warning(
                'Dados não encontrados para %s em %s', distribuidora, ano
            )
            return None

        realizados_dict = {}
        for item in dados_realizados:
            key = (item['sig_agente'], item['ide_conj'], item['sig_indicador'])
            realizados_dict[key] = item['valor_realizado']

        limites_dict = {}
        for item in dados_limites:
            key = (item['sig_agente'], item['ide_conj'], item['sig_indicador'])
            limites_dict[key] = item['valor_limite']

        scores_conjuntos = []
        for key, valor_realizado in realizados_dict.items():
            sig_agente, ide_conj, sig_indicador = key

            limite_key = (sig_agente, ide_conj, sig_indicador)
            if limite_key not in limites_dict:
                continue

            valor_limite = limites_dict[limite_key]
            desvio = calcular_desvio(valor_realizado, valor_limite)

            scores_conjuntos.append({
                'sig_agente': sig_agente,
                'ide_conj': ide_conj,
                'sig_indicador': sig_indicador,
                'valor_realizado': valor_realizado,
                'valor_limite': valor_limite,
                'desvio': desvio,
            })

        if not scores_conjuntos:
            logger.warning(
                'Nenhum conjunto com dados completos para %s em %s',
                distribuidora,
                ano,
            )
            return None

        conjuntos_scores: dict[str, dict] = {}
        for item in scores_conjuntos:
            ide_conj = item['ide_conj']
            if ide_conj not in conjuntos_scores:
                conjuntos_scores[ide_conj] = {
                    'sig_agente': item['sig_agente'],
                    'ide_conj': ide_conj,
                    'desvio_dec': 0.0,
                    'desvio_fec': 0.0,
                    'score_criticidade': 0.0,
                }

            if item['sig_indicador'] == 'DEC':
                conjuntos_scores[ide_conj]['desvio_dec'] = item['desvio']
            elif item['sig_indicador'] == 'FEC':
                conjuntos_scores[ide_conj]['desvio_fec'] = item['desvio']

        for conjunto in conjuntos_scores.values():
            conjunto['score_criticidade'] = (
                conjunto['desvio_dec'] + conjunto['desvio_fec']
            )

        scores_finais = [
            c['score_criticidade'] for c in conjuntos_scores.values()
        ]
        score_medio = sum(scores_finais) / len(scores_finais)

        desvio_dec_medio = sum(
            c['desvio_dec'] for c in conjuntos_scores.values()
        ) / len(conjuntos_scores)
        desvio_fec_medio = sum(
            c['desvio_fec'] for c in conjuntos_scores.values()
        ) / len(conjuntos_scores)

        resultado = {
            'ano': ano,
            'distribuidora': distribuidora.upper(),
            'score_criticidade': score_medio,
            'desvio_dec': desvio_dec_medio,
            'desvio_fec': desvio_fec_medio,
            'cor': classificar_criticidade(score_medio),
            'quantidade_conjuntos': len(conjuntos_scores),
        }

        await salvar_score_criticidade(resultado)
        logger.info(
            'Score calculado para %s em %s: %.2f',
            distribuidora,
            ano,
            score_medio,
        )
        return resultado

    except Exception as e:
        logger.error('Erro ao calcular score de criticidade: %s', e)
        raise


async def salvar_score_criticidade(dados: Dict) -> None:
    """Salva o score de criticidade na coleção MongoDB."""
    try:
        collection = get_mongo_collection('score_criticidade')
        filtro = {'ano': dados['ano'], 'distribuidora': dados['distribuidora']}
        await collection.update_one(filtro, {'$set': dados}, upsert=True)
        logger.info(
            'Score salvo para %s em %s',
            dados['distribuidora'],
            dados['ano'],
        )
    except Exception as e:
        logger.error('Erro ao salvar score de criticidade: %s', e)
        raise


async def criar_mapa_criticidade(
    distribuidora: str,
    ano: int,
    distribuidora_id: str,
    job_id: str | None = None,
) -> dict | None:
    """Calcula e salva o mapa de criticidade por conjunto."""
    dados_realizados = await buscar_dados_realizados(ano, distribuidora)
    if not dados_realizados:
        logger.warning(
            'Sem dados realizados para %s em %s', distribuidora, ano
        )
        return None

    dados_limites = await buscar_dados_limites(ano, distribuidora)

    realizados_dict = {}
    for item in dados_realizados:
        key = (item['sig_agente'], item['ide_conj'], item['sig_indicador'])
        realizados_dict[key] = item['valor_realizado']

    limites_dict = {}
    for item in dados_limites:
        key = (item['sig_agente'], item['ide_conj'], item['sig_indicador'])
        limites_dict[key] = item['valor_limite']

    conjuntos: dict[str, dict] = {}
    for key, valor_realizado in realizados_dict.items():
        sig_agente, ide_conj, sig_indicador = key
        limite = limites_dict.get((sig_agente, ide_conj, sig_indicador), 0.0)
        desvio = calcular_desvio(valor_realizado, limite)

        if ide_conj not in conjuntos:
            conjuntos[ide_conj] = {
                'ide_conj': ide_conj,
                'desvio_dec': 0.0,
                'desvio_fec': 0.0,
                'score_criticidade': 0.0,
            }
        if sig_indicador == 'DEC':
            conjuntos[ide_conj]['desvio_dec'] = round(desvio, 4)
        elif sig_indicador == 'FEC':
            conjuntos[ide_conj]['desvio_fec'] = round(desvio, 4)

    for c in conjuntos.values():
        score = c['desvio_dec'] + c['desvio_fec']
        c['score_criticidade'] = round(score, 4)
        c['categoria'] = classificar_criticidade(score)

    conjuntos_final = sorted(
        conjuntos.values(),
        key=lambda x: x['score_criticidade'],
        reverse=True,
    )

    documento = {
        'distribuidora_id': distribuidora_id,
        'distribuidora': distribuidora.upper(),
        'ano': ano,
        'job_id': job_id,
        'total_conjuntos': len(conjuntos_final),
        'conjuntos': conjuntos_final,
    }

    collection = get_mongo_collection('mapa_criticidade')
    await collection.update_one(
        {'distribuidora_id': distribuidora_id, 'ano': ano},
        {'$set': documento},
        upsert=True,
    )

    logger.info(
        'Mapa criticidade salvo. distribuidora=%s ano=%s conjuntos=%s',
        distribuidora.upper(),
        ano,
        len(conjuntos_final),
    )
    return documento

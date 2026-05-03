import logging

from backend.database import get_mongo_sync_db
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

WAIT_COUNTDOWN = 30
MAX_WAIT_RETRIES = 60


def _calcular_desvio(realizado: float, limite: float) -> float:
    if limite == 0:
        return 0.0
    return max(0.0, ((realizado - limite) / limite) * 100)


def _classificar_criticidade(score: float) -> str:
    if score == 0:
        return 'Verde'
    if 0 < score <= 10:
        return 'Laranja'
    return 'Vermelho'


def _buscar_realizados(db, ano: int, distribuidora: str) -> list[dict]:
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
    return list(db['dec_fec_realizado'].aggregate(pipeline))


def _buscar_limites(db, ano: int, distribuidora: str) -> list[dict]:
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
    return list(db['dec_fec_limite'].aggregate(pipeline))


@celery_app.task(
    bind=True, max_retries=MAX_WAIT_RETRIES, name='etl.score_criticidade'
)
def task_score_criticidade(
    self, job_id: str, distribuidora: str, ano: int
) -> dict:
    logger.info('[task_score_criticidade] Inicio. job_id=%s', job_id)

    db = get_mongo_sync_db()
    job = db['jobs'].find_one({'job_id': job_id})
    if not job or job.get('status') != 'completed':
        raise self.retry(countdown=WAIT_COUNTDOWN)

    dados_realizados = _buscar_realizados(db, ano, distribuidora)
    dados_limites = _buscar_limites(db, ano, distribuidora)

    if not dados_realizados or not dados_limites:
        logger.warning(
            '[task_score_criticidade] Dados não encontrados. distribuidora=%s ano=%s',
            distribuidora,
            ano,
        )
        return {'job_id': job_id, 'status': 'skipped', 'reason': 'no_data'}

    realizados_dict = {
        (r['sig_agente'], r['ide_conj'], r['sig_indicador']): r[
            'valor_realizado'
        ]
        for r in dados_realizados
    }
    limites_dict = {
        (l['sig_agente'], l['ide_conj'], l['sig_indicador']): l['valor_limite']
        for l in dados_limites
    }

    conjuntos: dict[str, dict] = {}
    for (
        sig_agente,
        ide_conj,
        sig_indicador,
    ), valor_realizado in realizados_dict.items():
        if (sig_agente, ide_conj, sig_indicador) not in limites_dict:
            continue
        desvio = _calcular_desvio(
            valor_realizado,
            limites_dict[(sig_agente, ide_conj, sig_indicador)],
        )
        if ide_conj not in conjuntos:
            conjuntos[ide_conj] = {
                'sig_agente': sig_agente,
                'ide_conj': ide_conj,
                'desvio_dec': 0.0,
                'desvio_fec': 0.0,
            }
        if sig_indicador == 'DEC':
            conjuntos[ide_conj]['desvio_dec'] = desvio
        elif sig_indicador == 'FEC':
            conjuntos[ide_conj]['desvio_fec'] = desvio

    if not conjuntos:
        logger.warning(
            '[task_score_criticidade] Nenhum conjunto com dados completos. distribuidora=%s ano=%s',
            distribuidora,
            ano,
        )
        return {
            'job_id': job_id,
            'status': 'skipped',
            'reason': 'no_complete_data',
        }

    for c in conjuntos.values():
        c['score_criticidade'] = c['desvio_dec'] + c['desvio_fec']

    scores = [c['score_criticidade'] for c in conjuntos.values()]
    score_medio = sum(scores) / len(scores)
    desvio_dec_medio = sum(c['desvio_dec'] for c in conjuntos.values()) / len(
        conjuntos
    )
    desvio_fec_medio = sum(c['desvio_fec'] for c in conjuntos.values()) / len(
        conjuntos
    )

    resultado = {
        'ano': ano,
        'distribuidora': distribuidora.upper(),
        'score_criticidade': score_medio,
        'desvio_dec': desvio_dec_medio,
        'desvio_fec': desvio_fec_medio,
        'cor': _classificar_criticidade(score_medio),
        'quantidade_conjuntos': len(conjuntos),
    }

    db['score_criticidade'].update_one(
        {'ano': ano, 'distribuidora': distribuidora.upper()},
        {'$set': resultado},
        upsert=True,
    )

    logger.info(
        '[task_score_criticidade] Concluida. job_id=%s score=%.2f',
        job_id,
        score_medio,
    )
    return {'job_id': job_id, 'status': 'done', 'score': score_medio}


@celery_app.task(
    bind=True, max_retries=MAX_WAIT_RETRIES, name='etl.mapa_criticidade'
)
def task_mapa_criticidade(
    self, job_id: str, distribuidora_id: str, distribuidora: str, ano: int
) -> dict:
    logger.info('[task_mapa_criticidade] Inicio. job_id=%s', job_id)

    db = get_mongo_sync_db()
    job = db['jobs'].find_one({'job_id': job_id})
    if not job or job.get('status') != 'completed':
        raise self.retry(countdown=WAIT_COUNTDOWN)

    dados_realizados = _buscar_realizados(db, ano, distribuidora)
    if not dados_realizados:
        logger.warning(
            '[task_mapa_criticidade] Sem dados realizados. distribuidora=%s ano=%s',
            distribuidora,
            ano,
        )
        return {'job_id': job_id, 'status': 'skipped', 'reason': 'no_data'}

    dados_limites = _buscar_limites(db, ano, distribuidora)

    realizados_dict = {
        (r['sig_agente'], r['ide_conj'], r['sig_indicador']): (
            r['valor_realizado'],
            r.get('dsc_conj', ''),
        )
        for r in dados_realizados
    }
    limites_dict = {
        (l['sig_agente'], l['ide_conj'], l['sig_indicador']): l['valor_limite']
        for l in dados_limites
    }

    conjuntos: dict[str, dict] = {}
    for (sig_agente, ide_conj, sig_indicador), (
        valor_realizado,
        dsc_conj,
    ) in realizados_dict.items():
        limite = limites_dict.get((sig_agente, ide_conj, sig_indicador), 0.0)
        desvio = _calcular_desvio(valor_realizado, limite)
        if ide_conj not in conjuntos:
            conjuntos[ide_conj] = {
                'ide_conj': ide_conj,
                'dsc_conj': dsc_conj,
                'dec_realizado': 0.0,
                'dec_limite': 0.0,
                'fec_realizado': 0.0,
                'fec_limite': 0.0,
                'desvio_dec': 0.0,
                'desvio_fec': 0.0,
                'score_criticidade': 0.0,
            }
        if sig_indicador == 'DEC':
            conjuntos[ide_conj]['desvio_dec'] = round(desvio, 4)
            conjuntos[ide_conj]['dec_realizado'] = round(valor_realizado, 4)
            conjuntos[ide_conj]['dec_limite'] = round(limite, 4)
        elif sig_indicador == 'FEC':
            conjuntos[ide_conj]['desvio_fec'] = round(desvio, 4)
            conjuntos[ide_conj]['fec_realizado'] = round(valor_realizado, 4)
            conjuntos[ide_conj]['fec_limite'] = round(limite, 4)

    for c in conjuntos.values():
        score = c['desvio_dec'] + c['desvio_fec']
        c['score_criticidade'] = round(score, 4)
        c['categoria'] = _classificar_criticidade(score)

    conjuntos_final = sorted(
        conjuntos.values(), key=lambda x: x['score_criticidade'], reverse=True
    )

    documento = {
        'distribuidora_id': distribuidora_id,
        'distribuidora': distribuidora.upper(),
        'ano': ano,
        'job_id': job_id,
        'total_conjuntos': len(conjuntos_final),
        'conjuntos': conjuntos_final,
    }

    db['mapa_criticidade'].update_one(
        {'distribuidora_id': distribuidora_id, 'ano': ano},
        {'$set': documento},
        upsert=True,
    )

    logger.info(
        '[task_mapa_criticidade] Concluida. job_id=%s conjuntos=%s',
        job_id,
        len(conjuntos_final),
    )
    return {
        'job_id': job_id,
        'status': 'done',
        'total_conjuntos': len(conjuntos_final),
    }

import logging

from backend.database import get_mongo_sync_db
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name='etl.dispatch_next_in_batch')
def task_dispatch_next_in_batch(batch_id: str | None = None) -> dict:
    if not batch_id:
        return {'skipped': True}

    try:
        db = get_mongo_sync_db()
        batch = db.batch_runs.find_one({'batch_id': batch_id}, {'_id': 0})
        if not batch:
            logger.warning('[task_dispatch_next_in_batch] Batch não encontrado. batch_id=%s', batch_id)
            return {'skipped': True}

        pending = [d for d in batch.get('distribuidoras', []) if d['status'] == 'pending']
        if not pending:
            logger.info('[task_dispatch_next_in_batch] Sem pendentes. batch_id=%s', batch_id)
            return {'done': True}

        next_item = pending[0]
        next_dist = {
            'id': next_item['id'],
            'dist_name': next_item['nome'],
            'date_gdb': next_item['ano'],
            'job_id': next_item.get('job_id'),
        }
        user_email = batch.get('user_email', '')

        logger.info(
            '[task_dispatch_next_in_batch] Disparando próxima. dist_id=%s batch_id=%s',
            next_item['id'], batch_id,
        )

        from backend.services.pipeline_batch import (
            DistribuidoraSemCNPJError,
            _trigger_pipeline_sync,
            _update_batch_dist_status,
        )
        try:
            _trigger_pipeline_sync(next_dist, user_email, db, batch_id)
        except DistribuidoraSemCNPJError as exc:
            logger.warning(
                '[task_dispatch_next_in_batch] Sem CNPJ, pulando. dist_id=%s motivo=%s',
                next_item['id'], exc,
            )
            if _update_batch_dist_status(db, batch_id, next_item['id'], 'skipped', str(exc)):
                task_dispatch_next_in_batch.apply_async(args=[batch_id])
            return {'skipped': next_item['id']}
        except Exception as exc:
            logger.exception(
                '[task_dispatch_next_in_batch] Falha ao disparar. dist_id=%s', next_item['id'],
            )
            if _update_batch_dist_status(db, batch_id, next_item['id'], 'failed', str(exc)):
                task_dispatch_next_in_batch.apply_async(args=[batch_id])
            return {'error': next_item['id']}

        return {'dispatched': next_item['id']}

    except Exception as exc:
        # Falha de infra (broker, MongoDB). Não propaga para não disparar o on_error
        # da chain — o dist_id do item atual já pode estar 'completed', e o on_error
        # não conseguiria atualizar o status nem despachar o próximo.
        logger.exception(
            '[task_dispatch_next_in_batch] Erro inesperado, reagendando. batch_id=%s', batch_id,
        )
        try:
            task_dispatch_next_in_batch.apply_async(args=[batch_id], countdown=60)
        except Exception:
            logger.exception(
                '[task_dispatch_next_in_batch] Falha ao reagendar. batch_id=%s', batch_id,
            )
        return {'retrying': str(exc)}

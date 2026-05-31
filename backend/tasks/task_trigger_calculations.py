import logging

from celery import chain

from backend.tasks.celery_app import celery_app
from backend.tasks.task_calculate_pt_pnt import task_calculate_pt_pnt
from backend.tasks.task_calculate_sam import task_calculate_sam
from backend.tasks.task_cleanup_files import task_cleanup_files
from backend.tasks.task_criticidade import (
    task_mapa_criticidade,
    task_score_criticidade,
)
from backend.tasks.task_dispatch_next_in_batch import (
    task_dispatch_next_in_batch,
)
from backend.tasks.task_finalize_batch import task_finalize_batch
from backend.tasks.task_on_calculation_failure import (
    task_on_calculation_failure,
)
from backend.tasks.task_tam import task_calcular_tam

logger = logging.getLogger(__name__)


@celery_app.task(name='etl.trigger_calculations')
def task_trigger_calculations(
    job_id: str,
    dist_id: str,
    sig_agente: str,
    ano: int,
    cnpj: str | None,
    batch_id: str | None = None,
) -> dict:
    logger.info(
        '[task_trigger_calculations] GDB pronto, disparando calculos. job_id=%s',
        job_id,
    )
    tasks = [
        task_score_criticidade.si(job_id, sig_agente, ano, cnpj),
        task_calculate_pt_pnt.si(job_id, dist_id, sig_agente, ano),
        task_calculate_sam.si(job_id, dist_id, sig_agente, ano),
        task_mapa_criticidade.si(job_id, dist_id, sig_agente, ano, cnpj),
        task_calcular_tam.si(
            job_id, {'id': dist_id, 'dist_name': sig_agente, 'date_gdb': ano}
        ),
        task_finalize_batch.si(job_id, batch_id, dist_id),
        task_cleanup_files.si(job_id),
    ]
    if batch_id:
        tasks.append(task_dispatch_next_in_batch.si(batch_id))

    chain(*tasks).on_error(
        task_on_calculation_failure.si(job_id, batch_id, dist_id)
    ).delay()
    return {'job_id': job_id}

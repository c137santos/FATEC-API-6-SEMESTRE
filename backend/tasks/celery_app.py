from celery import Celery
import os


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


# Instancia Celery
celery_app = Celery(
    'etl',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    include=[
        'backend.tasks.task_download_gdb',
        'backend.tasks.task_descompact_gdb',
        'backend.tasks.task_process_layers',
        'backend.tasks.task_load_dec_fec',
        'backend.tasks.task_calculate_pt_pnt',
        'backend.tasks.task_criticidade',
        'backend.tasks.task_tam',
        'backend.tasks.task_render_tam',
        'backend.tasks.task_render_criticidade',
        'backend.tasks.task_render_pt_and_pnt',
        'backend.tasks.task_calculate_sam',
    ],
)

celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
    worker_prefetch_multiplier=int(
        os.getenv('CELERY_PREFETCH_MULTIPLIER', '1')
    ),
    task_acks_late=_env_bool('CELERY_TASK_ACKS_LATE', True),
    task_reject_on_worker_lost=_env_bool(
        'CELERY_TASK_REJECT_ON_WORKER_LOST', True
    ),
    task_track_started=True,
)

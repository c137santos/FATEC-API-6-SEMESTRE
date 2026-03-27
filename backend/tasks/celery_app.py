from celery import Celery
import os

# Instancia Celery
celery_app = Celery(
    'etl',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    include=[
        'backend.tasks.task_download_gdb',
        'backend.tasks.task_descompact_gdb',
        'backend.tasks.task_process_layers',
    ],
)

celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
)

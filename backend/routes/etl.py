import uuid

from fastapi import APIRouter, HTTPException

from backend.core.schemas import DecFecRequest, DownloadRequest
from backend.services.etl_download import enqueue_download_gdb
from backend.tasks.task_load_dec_fec import (
    task_load_dec_fec_limite,
    task_load_dec_fec_realizado,
)

router = APIRouter()


@router.post('/download-gdb')
def download_gdb(request: DownloadRequest):
    try:
        return enqueue_download_gdb(str(request.url))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/load-dec-fec')
def load_dec_fec(request: DecFecRequest):
    job_id = str(uuid.uuid4())
    try:
        task_r = task_load_dec_fec_realizado.delay(
            job_id, str(request.url_realizado)
        )
        task_l = task_load_dec_fec_limite.delay(
            job_id, str(request.url_limite)
        )
        return {
            'job_id': job_id,
            'tasks': {
                'realizado': task_r.id,
                'limite': task_l.id,
            },
            'status': 'queued',
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import uuid

from fastapi import APIRouter, HTTPException

from backend.schemas import DownloadRequest
from backend.tasks.task_download_gdb import task_download_gdb


router = APIRouter()


@router.post('/download-gdb')
def download_gdb(request: DownloadRequest):
    job_id = str(uuid.uuid4())
    try:
        task = task_download_gdb.delay(job_id, str(request.url))
        return {"job_id": job_id, "task_id": task.id, "status": "queued"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


import uuid

from backend.tasks.task_download_gdb import task_download_gdb


def enqueue_download_gdb(
    url: str, distribuidora_id: str | None = None
) -> dict[str, str]:
    """Enqueue the GDB download task and return queue metadata."""
    job_id = str(uuid.uuid4())
    task = task_download_gdb.delay(job_id, url, distribuidora_id)
    return {
        'job_id': job_id,
        'task_id': task.id,
        'status': 'queued',
    }

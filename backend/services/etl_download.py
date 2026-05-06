import uuid

from backend.tasks.task_download_gdb import task_download_gdb


def create_job_id() -> str:
    return str(uuid.uuid4())


def enqueue_download_gdb(
    job_id: str,
    url: str,
    distribuidora_id: str | None = None,
) -> dict[str, str]:
    """Enqueue the GDB download task and return queue metadata."""
    task = task_download_gdb.delay(job_id, url, distribuidora_id)
    return {
        'job_id': job_id,
        'task_id': task.id,
        'status': 'queued',
    }

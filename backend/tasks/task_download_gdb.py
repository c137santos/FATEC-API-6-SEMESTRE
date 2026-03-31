import logging
import os
from pathlib import Path
import zipfile

import httpx
from celery import signature

from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = Path(os.getenv('DOWNLOAD_DIR', '/data/downloads/'))

@celery_app.task(bind=True, max_retries=2, default_retry_delay=60, name="etl.download_gdb")
def task_download_gdb(self, job_id: str, url: str) -> dict:
    logger.info("[task_download_gdb] Inicio do download. job_id=%s url=%s", job_id, url)

    if not url:
        logger.error("[task_download_gdb] URL ausente. job_id=%s", job_id)
        raise RuntimeError("URL de download não fornecida")

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DOWNLOAD_DIR / f"{job_id}.zip"

    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=300) as r:
            r.raise_for_status()
            headers = getattr(r, "headers", {}) or {}
            content_length = headers.get("content-length", "unknown")
            status_code = getattr(r, "status_code", "unknown")
            logger.info(
                "[task_download_gdb] Resposta recebida. job_id=%s status=%s content_length=%s",
                job_id,
                status_code,
                content_length,
            )

            total_bytes = 0
            with open(zip_path, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=8192):
                    f.write(chunk)
                    total_bytes += len(chunk)

        logger.info(
            "[task_download_gdb] Download concluido. job_id=%s destino=%s bytes=%s",
            job_id,
            zip_path,
            total_bytes,
        )

        # Valida ZIP
        if not zipfile.is_zipfile(zip_path):
            logger.error(
                "[task_download_gdb] Arquivo invalido (nao e ZIP). job_id=%s arquivo=%s",
                job_id,
                zip_path,
            )
            zip_path.unlink(missing_ok=True)
            raise RuntimeError("Arquivo baixado não é um ZIP válido")

        # Enfileira próxima task com assinatura Celery válida.
        signature('etl.extrair_gdb', args=(job_id, str(zip_path))).delay()
        logger.info(
            "[task_download_gdb] Proxima task enfileirada. job_id=%s next_task=etl.extrair_gdb zip_path=%s",
            job_id,
            zip_path,
        )

        return {"job_id": job_id, "zip_path": str(zip_path), "status": "downloaded"}

    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning(
            "[task_download_gdb] Erro de rede. job_id=%s tentativa=%s/%s erro=%s",
            job_id,
            self.request.retries + 1,
            self.max_retries,
            exc,
        )
        zip_path.unlink(missing_ok=True)
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.exception("[task_download_gdb] Falha inesperada. job_id=%s erro=%s", job_id, exc)
        zip_path.unlink(missing_ok=True)
        raise

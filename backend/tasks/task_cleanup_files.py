import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from backend.database import get_mongo_sync_db
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = Path(os.getenv('DOWNLOAD_DIR', '/data/downloads/'))
TMP_DIR = Path(os.getenv('TMP_DIR', '/data/tmp/'))


def _iter_render_paths(render_paths: dict):
    for value in render_paths.values():
        if isinstance(value, dict):
            yield from value.values()
        else:
            yield value


@celery_app.task(bind=True, name='etl.cleanup_files')
def task_cleanup_files(self, job_id: str) -> dict:
    logger.info('[task_cleanup_files] Inicio. job_id=%s', job_id)

    removed = []
    errors = []

    zip_path = DOWNLOAD_DIR / f'{job_id}.zip'
    if zip_path.exists():
        try:
            zip_path.unlink()
            removed.append(str(zip_path))
            logger.info('[task_cleanup_files] ZIP removido. job_id=%s path=%s', job_id, zip_path)
        except Exception as exc:
            errors.append(str(zip_path))
            logger.warning('[task_cleanup_files] Falha ao remover ZIP. job_id=%s path=%s erro=%s', job_id, zip_path, exc)

    tmp_dir = TMP_DIR / job_id
    if tmp_dir.exists():
        try:
            shutil.rmtree(tmp_dir)
            removed.append(str(tmp_dir))
            logger.info('[task_cleanup_files] Diretorio temporario removido. job_id=%s path=%s', job_id, tmp_dir)
        except Exception as exc:
            errors.append(str(tmp_dir))
            logger.warning('[task_cleanup_files] Falha ao remover diretorio temporario. job_id=%s path=%s erro=%s', job_id, tmp_dir, exc)

    try:
        db = get_mongo_sync_db()
        job_doc = db['jobs'].find_one({'job_id': job_id}, {'render_paths': 1, '_id': 0})
        for img_path_str in _iter_render_paths((job_doc or {}).get('render_paths') or {}):
            if not img_path_str:
                continue
            img_path = Path(img_path_str)
            if img_path.exists():
                try:
                    img_path.unlink()
                    removed.append(str(img_path))
                    logger.info('[task_cleanup_files] Imagem removida. job_id=%s path=%s', job_id, img_path)
                except Exception as exc:
                    errors.append(str(img_path))
                    logger.warning('[task_cleanup_files] Falha ao remover imagem. job_id=%s path=%s erro=%s', job_id, img_path, exc)

        db['jobs'].update_one(
            {'job_id': job_id},
            {'$set': {
                'cleanup_status': 'failed' if errors else 'completed',
                'cleanup_removed': removed,
                'cleanup_errors': errors,
                'cleanup_at': datetime.utcnow(),
            }},
        )
    except Exception as exc:
        logger.warning('[task_cleanup_files] Falha ao acessar MongoDB. job_id=%s erro=%s', job_id, exc)

    logger.info(
        '[task_cleanup_files] Concluido. job_id=%s removidos=%s erros=%s',
        job_id, len(removed), len(errors),
    )
    return {'job_id': job_id, 'removed': removed, 'errors': errors}
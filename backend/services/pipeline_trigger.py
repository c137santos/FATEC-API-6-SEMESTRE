import uuid
from datetime import datetime, timezone

from backend.tasks.task_render_sam import task_render_sam
import httpx
from celery import chain
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import Distribuidora
from backend.tasks.task_calculate_pt_pnt import task_calculate_pt_pnt
from backend.tasks.task_calculate_sam import task_calculate_sam
from backend.tasks.task_criticidade import (
    task_mapa_criticidade,
    task_score_criticidade,
)
from backend.tasks.task_download_gdb import DOWNLOAD_DIR, task_download_gdb
from backend.tasks.task_descompact_gdb import task_descompact_gdb
from backend.tasks.task_render_criticidade import (
    task_render_mapa_calor,
    task_render_tabela_score,
)
from backend.tasks.task_render_pt_and_pnt import task_render_pt_pnt
from backend.tasks.task_tam import task_calcular_tam
from backend.tasks.task_render_tam import task_render_grafico_tam
from backend.tasks.task_report import task_gerar_report
from backend.tasks.task_cleanup_files import task_cleanup_files
from backend.database import get_mongo_async_db

ARCGIS_ITEM_URL = 'https://www.arcgis.com/sharing/rest/content/items/{item_id}'
ARCGIS_DOWNLOAD_URL = (
    'https://www.arcgis.com/sharing/rest/content/items/{item_id}/data'
)
ALLOWED_ITEM_TYPES = {'Feature Service', 'File Geodatabase'}


async def _get_distribuidora_name(
    session: AsyncSession,
    distribuidora_id: str,
    ano: int,
) -> str:
    stmt = select(Distribuidora.dist_name).where(
        Distribuidora.id == distribuidora_id,
        Distribuidora.date_gdb == ano,
    )
    result = await session.execute(stmt)
    dist_name = result.scalar_one_or_none()
    if not dist_name:
        raise LookupError('Distribuidora não encontrada para o ano informado')
    return dist_name


async def distribuidora_job_already_triggered(
    session: AsyncSession,
    distribuidora_id: str,
    ano: int,
) -> bool:
    stmt = select(Distribuidora.job_id).where(
        Distribuidora.id == distribuidora_id,
        Distribuidora.date_gdb == ano,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def save_distribuidora_job_tracking(
    session: AsyncSession,
    distribuidora_id: str,
    ano: int,
    job_id: str,
) -> None:
    stmt = (
        update(Distribuidora)
        .where(
            Distribuidora.id == distribuidora_id,
            Distribuidora.date_gdb == ano,
        )
        .values(
            job_id=job_id,
            processed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    await session.execute(stmt)
    await session.commit()


async def init_tam_metadata(
    session: AsyncSession,
    distribuidora_id: str,
    ano: int,
    job_id: str,
) -> None:
    """Inicializa os dados do Job no MongoDB para que as tasks futuras tenham acesso."""
    
    stmt = select(Distribuidora.dist_name).where(
        Distribuidora.id == distribuidora_id,
        Distribuidora.date_gdb == ano,
    )

    result = await session.execute(stmt)
    dist_name = result.scalar_one_or_none()

    db = get_mongo_async_db()
    
    await db.jobs.insert_one({
        "job_id": job_id,
        "distribuidora_id": distribuidora_id,
        "dist_name": dist_name,  
        "ano_gdb": ano,          
        "status": "started",
        "created_at": datetime.utcnow()
    })


async def trigger_pipeline_flow(
    session: AsyncSession,
    distribuidora_id: str,
    ano: int,
) -> dict:
    """Orquestra todos os passos da pipeline: download + criticidade + render."""
    if await distribuidora_job_already_triggered(
        session, distribuidora_id, ano
    ):
        raise ValueError(
            'Pipeline já foi acionada para a distribuidora no ano informado'
        )

    dist_name = await _get_distribuidora_name(
        session,
        distribuidora_id,
        ano,
    )

    download_url = ARCGIS_DOWNLOAD_URL.format(item_id=distribuidora_id)
    job_id = str(uuid.uuid4())
    zip_path = str(DOWNLOAD_DIR / f'{job_id}.zip')

    result = chain(
        task_download_gdb.si(job_id, download_url, distribuidora_id),
        task_descompact_gdb.si(job_id, zip_path, distribuidora_id),
        task_score_criticidade.si(job_id, dist_name, ano),
        task_calculate_pt_pnt.si(job_id, distribuidora_id, dist_name, ano),
        task_render_pt_pnt.si(job_id, distribuidora_id, dist_name, ano),
        task_calculate_sam.si(job_id, distribuidora_id, dist_name, ano),
        task_mapa_criticidade.si(job_id, distribuidora_id, dist_name, ano),
        task_calcular_tam.si(job_id, {
            "id": distribuidora_id, 
            "dist_name": dist_name, 
            "date_gdb": ano
        }),       
        task_render_grafico_tam.si(job_id),
        task_render_tabela_score.si(job_id, dist_name, ano),
        task_render_mapa_calor.si(job_id, dist_name, ano),
        task_render_sam.si(job_id, distribuidora_id, dist_name, ano),
        task_gerar_report.si(job_id),
        task_cleanup_files.si(job_id),
    ).delay()

    await save_distribuidora_job_tracking(
        session=session,
        distribuidora_id=distribuidora_id,
        ano=ano,
        job_id=job_id,
    )

    await init_tam_metadata(
        session=session, 
        distribuidora_id=distribuidora_id, 
        ano=ano, 
        job_id=job_id
    )

    return {
        'job_id': job_id,
        'task_id': result.id,
        'status': 'queued',
        'distribuidora_id': distribuidora_id,
        'ano': ano,
        'download_url': download_url,
    }

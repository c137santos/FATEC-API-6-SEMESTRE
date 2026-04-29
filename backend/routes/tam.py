import logging
from fastapi import APIRouter, Depends, HTTPException
import os
from motor.motor_asyncio import AsyncIOMotorClient
from ..core.calculo_tam import calculo_tam
import asyncpg
from settings import Settings

logger = logging.getLogger(__name__)

router = APIRouter()
settings = Settings()


async def get_pg_db():
    pg_url = "postgresql://" + settings.DATABASE_URL.split("://")[-1]

    try:
        conn = await asyncpg.connect(pg_url)
        try:
            yield conn
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Erro ao conectar no Postgres via asyncpg: {e}")
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco de dados.")

async def get_db():

    uri = os.getenv('MONGO_URI')
    db_name = os.getenv('MONGO_DB')

    if not uri:
        raise HTTPException(
            status_code=500, detail='Configuração ausente: MONGO_URI'
        )
    if not db_name:
        raise HTTPException(
            status_code=500, detail='Configuração ausente: MONGO_DB'
        )

    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)

    try:
        yield client[db_name]
    finally:
        client.close()


@router.get("/tam/{job_id}")
async def get_tam_route(
    job_id: str, 
    pg_db: asyncpg.Connection = Depends(get_pg_db), 
    mongo_db = Depends(get_db)
):
    try:
        trechos, ranking, top10 = await calculo_tam(mongo_db, job_id, pg_db)
        return {
            "status": "success",
            "metadata": {
                "job_id": job_id,
                "distribuidora_info": ranking[0] if ranking else {}
            },
            "data": {
                "trechos": trechos,
                "ranking_por_conjunto": ranking,
                "top_10": top10
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
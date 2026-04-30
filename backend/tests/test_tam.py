import pytest
from sqlalchemy import text
from unittest.mock import patch


@pytest.fixture(autouse=True)
def mock_external_deps(mongo_db):
    """
    Isola o teste de dependências externas:
    1. MongoDB via database.py (Garante loop correto)
    2. Celery via local original da função (Evita Broker Connection Error)
    """
    with patch("backend.database.get_mongo_async_db", return_value=mongo_db), \
         patch("backend.services.etl_download.enqueue_download_gdb") as mock_enqueue:
        
        mock_enqueue.return_value = {
            "job_id": "7d098e09-35de-4127-947c-a30a80964ac7",
            "status": "queued"
        }
        
        yield mock_enqueue


@pytest.mark.asyncio
async def test_trigger_pipeline_flow_data_integrity(session, mongo_db, triggered_job):
    job_id_api = str(triggered_job["job_id"])
    dist_id = triggered_job["dist_data"]["id"]
    ano = triggered_job["dist_data"]["date_gdb"]

    stmt = text("SELECT job_id FROM distribuidoras WHERE id = :id AND date_gdb = :ano")
    result = await session.execute(stmt, {"id": dist_id, "ano": ano})
    db_job_id = result.scalar()
    
    assert str(db_job_id) == job_id_api, f"Postgres divergiu! API: {job_id_api} vs DB: {db_job_id}"

    job_doc = await mongo_db['jobs'].find_one({"job_id": job_id_api})

    if not job_doc:
        backup_doc = await mongo_db['jobs'].find_one({"distribuidora_id": dist_id, "ano_gdb": ano})
        id_no_mongo = backup_doc['job_id'] if backup_doc else "NADA"
        pytest.fail(f"O Mongo não salvou o job_id da API ({job_id_api}). Encontrado no Mongo: {id_no_mongo}")

    assert str(job_doc['job_id']) == job_id_api
    assert job_doc['status'] == "started"
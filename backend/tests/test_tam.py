import pytest
from sqlalchemy import text
from unittest.mock import patch


@pytest.fixture(autouse=True)
def mock_external_deps(mongo_db):
    """
    Isola o teste de dependências externas.
    """
    with patch("backend.database.get_mongo_async_db", return_value=mongo_db), \
         patch("backend.services.etl_download.enqueue_download_gdb") as mock_enqueue:
        
        yield mock_enqueue


@pytest.mark.asyncio
async def test_trigger_pipeline_flow_data_integrity(session, mongo_db, triggered_job):
    job_id_api = str(triggered_job["job_id"])
    dist_id = triggered_job["dist_data"]["id"]
    ano = triggered_job["dist_data"]["date_gdb"]

    stmt = text("SELECT job_id FROM distribuidoras WHERE id = :id AND date_gdb = :ano")
    result = await session.execute(stmt, {"id": dist_id, "ano": ano})
    db_job_id = result.scalar()
    assert str(db_job_id) == job_id_api

    job_doc = await mongo_db['jobs'].find_one({"job_id": job_id_api})

    if not job_doc:
        all_jobs = await mongo_db['jobs'].find({"distribuidora_id": dist_id}).to_list(length=10)
        ids_presentes = [j['job_id'] for j in all_jobs]
        pytest.fail(f"Job {job_id_api} não encontrado. IDs no banco para esta dist: {ids_presentes}")

    assert str(job_doc['job_id']) == job_id_api
    assert job_doc['status'] == "started"
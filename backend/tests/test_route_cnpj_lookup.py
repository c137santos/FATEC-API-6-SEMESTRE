import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_cnpj_lookup_distribuidora_not_found(client):
    response = await client.post('/dist/distribuidoras/nao-existe/cnpj-lookup')

    assert response.status_code == 404
    assert response.json()['detail'] == 'Distribuidora não encontrada'


@pytest.mark.asyncio
async def test_cnpj_lookup_already_matched_returns_409(client, session):
    dist_id = 'dist-matched-1'
    await session.execute(
        text("INSERT INTO distribuidoras (id, date_gdb, dist_name) VALUES (:id, 2024, :name)"),
        {'id': dist_id, 'name': 'DIST MATCHED'},
    )
    await session.execute(
        text(
            "INSERT INTO distribuidora_cnpj (dist_id, cnpj_enrichment_status)"
            " VALUES (:dist_id, 'matched')"
        ),
        {'dist_id': dist_id},
    )
    await session.commit()

    response = await client.post(f'/dist/distribuidoras/{dist_id}/cnpj-lookup')

    assert response.status_code == 409
    assert response.json()['detail'] == 'Distribuidora já possui CNPJ resolvido'


@pytest.mark.asyncio
async def test_cnpj_lookup_no_match_returns_501(client, session):
    dist_id = 'dist-no-match-1'
    await session.execute(
        text("INSERT INTO distribuidoras (id, date_gdb, dist_name) VALUES (:id, 2024, :name)"),
        {'id': dist_id, 'name': 'DIST NO MATCH'},
    )
    await session.execute(
        text(
            "INSERT INTO distribuidora_cnpj (dist_id, cnpj_enrichment_status)"
            " VALUES (:dist_id, 'no_match')"
        ),
        {'dist_id': dist_id},
    )
    await session.commit()

    response = await client.post(f'/dist/distribuidoras/{dist_id}/cnpj-lookup')

    assert response.status_code == 501
    assert response.json()['detail'] == 'External CNPJ lookup not yet configured'

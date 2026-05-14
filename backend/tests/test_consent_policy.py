from http import HTTPStatus


async def test_get_latest_consent_policy(client, consent_policy):
    response = await client.get('/consent-policy/latest')

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['version'] == consent_policy.version
    assert data['content'] == consent_policy.content

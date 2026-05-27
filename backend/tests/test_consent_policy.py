from http import HTTPStatus


async def test_get_latest_consent_policy(client, consent_policy):
    response = await client.get('/consent-policy/latest')

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['version'] == consent_policy.version
    assert data['content'] == consent_policy.content
    assert data['is_mandatory'] is True


async def test_get_latest_all_returns_both_policy_types(client, consent_policy, optional_consent_policy):
    response = await client.get('/consent-policy/latest-all')

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['mandatory']['id'] == consent_policy.id
    assert data['mandatory']['is_mandatory'] is True
    assert data['optional']['id'] == optional_consent_policy.id
    assert data['optional']['is_mandatory'] is False



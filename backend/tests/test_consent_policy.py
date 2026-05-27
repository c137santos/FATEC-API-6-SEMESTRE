from http import HTTPStatus

from backend.core.models import UserConsent


async def test_get_latest_consent_policy(client, consent_policy):
    response = await client.get('/consent-policy/latest')

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['version'] == consent_policy.version
    assert data['content'] == consent_policy.content
    assert data['is_mandatory'] is True


async def test_get_latest_returns_mandatory_even_when_optional_has_higher_id(
    client, consent_policy, optional_consent_policy
):
    # optional_consent_policy is created after consent_policy, so it has a
    # higher id — the endpoint must still return the mandatory policy.
    assert optional_consent_policy.id > consent_policy.id

    response = await client.get('/consent-policy/latest')

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['id'] == consent_policy.id
    assert data['is_mandatory'] is True


async def test_get_latest_all_returns_both_policy_types(client, consent_policy, optional_consent_policy):
    response = await client.get('/consent-policy/latest-all')

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['mandatory']['id'] == consent_policy.id
    assert data['mandatory']['is_mandatory'] is True
    assert data['optional']['id'] == optional_consent_policy.id
    assert data['optional']['is_mandatory'] is False


async def test_get_my_consents_returns_user_consent_records(
    client, session, user, token, consent_policy, optional_consent_policy
):
    session.add(UserConsent(
        user_id=user.id,
        consent_policy_id=consent_policy.id,
        accepted=True,
    ))
    session.add(UserConsent(
        user_id=user.id,
        consent_policy_id=optional_consent_policy.id,
        accepted=False,
    ))
    await session.flush()

    response = await client.get(
        '/users/me/consents',
        cookies={'access_token': token},
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert len(data) == 2

    mandatory = next(c for c in data if c['is_mandatory'] is True)
    optional = next(c for c in data if c['is_mandatory'] is False)

    assert mandatory['accepted'] is True
    assert mandatory['policy_version'] == consent_policy.version
    assert optional['accepted'] is False
    assert optional['policy_version'] == optional_consent_policy.version


async def test_get_my_consents_requires_authentication(client):
    response = await client.get('/users/me/consents')

    assert response.status_code == HTTPStatus.UNAUTHORIZED



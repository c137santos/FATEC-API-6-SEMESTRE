from http import HTTPStatus

from sqlalchemy import select

from backend.core.oauth_models import OAuth2Client


async def test_register_client_returns_credentials(client):
    response = await client.post(
        '/oauth/clients',
        json={
            'client_name': 'Test App',
            'redirect_uris': ['http://localhost/callback'],
            'allowed_scopes': ['openid', 'email'],
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert 'client_id' in data
    assert data['client_id']


async def test_public_client_has_no_stored_secret(client, session):
    response = await client.post(
        '/oauth/clients',
        json={
            'client_name': 'Public App',
            'redirect_uris': ['http://localhost/cb'],
            'allowed_scopes': ['openid'],
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    client_id = response.json()['client_id']

    db_client = await session.scalar(
        select(OAuth2Client).where(OAuth2Client.client_id == client_id)
    )
    assert db_client.client_secret is None


async def test_same_name_creates_distinct_clients(client):
    payload = {
        'client_name': 'Duplicate App',
        'redirect_uris': ['http://localhost/cb'],
        'allowed_scopes': ['openid'],
    }
    r1 = await client.post('/oauth/clients', json=payload)
    r2 = await client.post('/oauth/clients', json=payload)

    assert r1.status_code == HTTPStatus.CREATED
    assert r2.status_code == HTTPStatus.CREATED
    assert r1.json()['client_id'] != r2.json()['client_id']


async def test_missing_field_returns_422(client):
    response = await client.post(
        '/oauth/clients',
        json={'client_name': 'Incomplete App'},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_redirect_uris_and_scopes_stored(client, session):
    response = await client.post(
        '/oauth/clients',
        json={
            'client_name': 'Scoped App',
            'redirect_uris': ['https://app.example.com/cb', 'https://app.example.com/cb2'],
            'allowed_scopes': ['openid', 'email', 'profile'],
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    client_id = response.json()['client_id']

    db_client = await session.scalar(
        select(OAuth2Client).where(OAuth2Client.client_id == client_id)
    )
    assert db_client.client_name == 'Scoped App'
    assert 'https://app.example.com/cb' in db_client.redirect_uris
    allowed = db_client.get_allowed_scope('openid email profile')
    assert allowed == 'openid email profile'

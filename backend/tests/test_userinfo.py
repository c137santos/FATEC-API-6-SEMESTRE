import base64
import hashlib
from http import HTTPStatus
from urllib.parse import parse_qs, urlparse

from backend.core.oauth_models import OAuth2Token

REDIRECT_URI = 'http://localhost/callback'
VERIFIER = 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk'


def _challenge(verifier: str = VERIFIER) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode()


async def _full_token_exchange(
    client, oauth_client, token, scope='openid email profile'
):
    challenge = _challenge()
    approve = await client.post(
        '/oauth/authorize',
        data={
            'action': 'allow',
            'client_id': oauth_client['client_id'],
            'redirect_uri': REDIRECT_URI,
            'scope': scope,
            'state': 's',
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
            'response_type': 'code',
        },
        follow_redirects=False,
    )
    parsed = urlparse(approve.headers['location'])
    code = parse_qs(parsed.query)['code'][0]

    resp = await client.post(
        '/oauth/token',
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'code_verifier': VERIFIER,
            'client_id': oauth_client['client_id'],
            'redirect_uri': REDIRECT_URI,
        },
    )
    return resp.json()


async def test_userinfo_returns_sub(client, oauth_client, user, token):
    tokens = await _full_token_exchange(client, oauth_client, token)
    response = await client.get(
        '/oauth/userinfo',
        headers={'Authorization': f'Bearer {tokens["access_token"]}'},
    )
    assert response.status_code == HTTPStatus.OK
    assert 'sub' in response.json()


async def test_userinfo_email_scope_returns_email(
    client, oauth_client, user, token
):
    tokens = await _full_token_exchange(
        client, oauth_client, token, scope='openid email'
    )
    data = await client.get(
        '/oauth/userinfo',
        headers={'Authorization': f'Bearer {tokens["access_token"]}'},
    )
    assert data.status_code == HTTPStatus.OK
    body = data.json()
    assert body['email'] == user.email
    assert 'username' not in body


async def test_userinfo_profile_scope_returns_username(
    client, oauth_client, user, token
):
    tokens = await _full_token_exchange(
        client, oauth_client, token, scope='openid profile'
    )
    data = await client.get(
        '/oauth/userinfo',
        headers={'Authorization': f'Bearer {tokens["access_token"]}'},
    )
    assert data.status_code == HTTPStatus.OK
    body = data.json()
    assert body['username'] == user.username
    assert 'email' not in body


async def test_userinfo_no_header_returns_401(client):
    response = await client.get('/oauth/userinfo')
    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_userinfo_invalid_token_returns_401(client):
    response = await client.get(
        '/oauth/userinfo',
        headers={'Authorization': 'Bearer invalid-token-xxxx'},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_userinfo_token_without_openid_scope_returns_403(
    client, session, user
):
    token_obj = OAuth2Token(
        client_id='test-client',
        user_id=user.id,
        access_token='no-openid-scope-token',
        token_type='Bearer',
        scope='email profile',
        expires_in=3600,
    )
    session.add(token_obj)
    await session.commit()

    response = await client.get(
        '/oauth/userinfo',
        headers={'Authorization': 'Bearer no-openid-scope-token'},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


async def test_refresh_token_issues_new_access_token(
    client, oauth_client, user, token
):
    tokens = await _full_token_exchange(client, oauth_client, token)

    response = await client.post(
        '/oauth/token',
        data={
            'grant_type': 'refresh_token',
            'refresh_token': tokens['refresh_token'],
            'client_id': oauth_client['client_id'],
        },
    )
    assert response.status_code == HTTPStatus.OK, response.json()
    data = response.json()
    assert 'access_token' in data
    assert data['access_token'] != tokens['access_token']


async def test_old_access_token_rejected_after_refresh(
    client, oauth_client, user, token
):
    tokens = await _full_token_exchange(client, oauth_client, token)
    old_access = tokens['access_token']

    await client.post(
        '/oauth/token',
        data={
            'grant_type': 'refresh_token',
            'refresh_token': tokens['refresh_token'],
            'client_id': oauth_client['client_id'],
        },
    )

    response = await client.get(
        '/oauth/userinfo',
        headers={'Authorization': f'Bearer {old_access}'},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED

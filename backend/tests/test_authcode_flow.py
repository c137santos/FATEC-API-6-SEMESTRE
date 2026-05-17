import base64
import hashlib
import json
from http import HTTPStatus
from urllib.parse import parse_qs, urlparse


def _pkce_pair(
    verifier: str = 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk',
) -> tuple:
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
    return verifier, challenge


REDIRECT_URI = 'http://localhost/callback'


async def test_authorize_unknown_client_returns_400(client):
    response = await client.get(
        '/oauth/authorize',
        params={
            'client_id': 'nonexistent',
            'redirect_uri': REDIRECT_URI,
            'response_type': 'code',
            'scope': 'openid',
            'state': 'xyz',
            'code_challenge': 'abc',
            'code_challenge_method': 'S256',
        },
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST


async def test_authorize_unauthenticated_redirects_to_login(
    client, oauth_client
):
    verifier, challenge = _pkce_pair()
    response = await client.get(
        '/oauth/authorize',
        params={
            'client_id': oauth_client['client_id'],
            'redirect_uri': REDIRECT_URI,
            'response_type': 'code',
            'scope': 'openid',
            'state': 'xyz',
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
        },
        follow_redirects=False,
    )
    assert response.status_code == HTTPStatus.FOUND
    location = response.headers['location']
    assert '/login.html' in location
    assert 'next=' in location


async def test_authorize_authenticated_redirects_to_consent(
    client, oauth_client, token
):
    verifier, challenge = _pkce_pair()
    response = await client.get(
        '/oauth/authorize',
        params={
            'client_id': oauth_client['client_id'],
            'redirect_uri': REDIRECT_URI,
            'response_type': 'code',
            'scope': 'openid email',
            'state': 'xyz',
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
        },
        follow_redirects=False,
    )
    assert response.status_code == HTTPStatus.FOUND
    location = response.headers['location']
    assert '/consent.html' in location
    assert 'client_id=' in location
    assert 'code_challenge=' in location
    assert 'state=xyz' in location


async def test_approve_consent_redirects_with_code(
    client, oauth_client, token
):
    verifier, challenge = _pkce_pair()
    response = await client.post(
        '/oauth/authorize',
        data={
            'action': 'allow',
            'client_id': oauth_client['client_id'],
            'redirect_uri': REDIRECT_URI,
            'scope': 'openid',
            'state': 'xyz',
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
            'response_type': 'code',
        },
        follow_redirects=False,
    )
    assert response.status_code == HTTPStatus.FOUND
    location = response.headers['location']
    assert 'code=' in location
    assert 'state=xyz' in location
    assert 'error' not in location


async def _get_auth_code(client, oauth_client, token) -> tuple[str, str]:
    verifier, challenge = _pkce_pair()
    response = await client.post(
        '/oauth/authorize',
        data={
            'action': 'allow',
            'client_id': oauth_client['client_id'],
            'redirect_uri': REDIRECT_URI,
            'scope': 'openid email',
            'state': 'xyz',
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
            'response_type': 'code',
        },
        follow_redirects=False,
    )
    parsed = urlparse(response.headers['location'])
    code = parse_qs(parsed.query)['code'][0]
    return code, verifier


async def test_token_endpoint_returns_tokens(
    client, oauth_client, user, token
):
    code, verifier = await _get_auth_code(client, oauth_client, token)

    response = await client.post(
        '/oauth/token',
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'code_verifier': verifier,
            'client_id': oauth_client['client_id'],
            'redirect_uri': REDIRECT_URI,
        },
    )
    assert response.status_code == HTTPStatus.OK, response.json()
    data = response.json()
    assert 'access_token' in data
    assert 'refresh_token' in data
    assert 'id_token' in data
    assert data.get('token_type', '').lower() == 'bearer'


async def test_token_endpoint_wrong_verifier_returns_400(
    client, oauth_client, user, token
):
    code, _ = await _get_auth_code(client, oauth_client, token)

    response = await client.post(
        '/oauth/token',
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'code_verifier': 'wrong-verifier-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'client_id': oauth_client['client_id'],
            'redirect_uri': REDIRECT_URI,
        },
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST


async def test_full_end_to_end_flow(client, oauth_client, user, token):
    verifier, challenge = _pkce_pair()

    # Step 1: get authorization code
    approve = await client.post(
        '/oauth/authorize',
        data={
            'action': 'allow',
            'client_id': oauth_client['client_id'],
            'redirect_uri': REDIRECT_URI,
            'scope': 'openid email profile',
            'state': 'end2end',
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
            'response_type': 'code',
        },
        follow_redirects=False,
    )
    assert approve.status_code == HTTPStatus.FOUND
    parsed = urlparse(approve.headers['location'])
    code = parse_qs(parsed.query)['code'][0]

    # Step 2: exchange code for tokens
    token_resp = await client.post(
        '/oauth/token',
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'code_verifier': verifier,
            'client_id': oauth_client['client_id'],
            'redirect_uri': REDIRECT_URI,
        },
    )
    assert token_resp.status_code == HTTPStatus.OK, token_resp.json()
    data = token_resp.json()
    assert data['access_token']
    assert data['refresh_token']
    assert data['id_token']

    # Decode ID token header to verify it's HS256
    header_b64 = data['id_token'].split('.')[0]
    header_b64 += '=' * (-len(header_b64) % 4)
    header = json.loads(base64.urlsafe_b64decode(header_b64))
    assert header['alg'] == 'HS256'


async def test_deny_consent_redirects_with_error(client, oauth_client, token):
    verifier, challenge = _pkce_pair()
    response = await client.post(
        '/oauth/authorize',
        data={
            'action': 'deny',
            'client_id': oauth_client['client_id'],
            'redirect_uri': REDIRECT_URI,
            'scope': 'openid',
            'state': 'xyz',
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
            'response_type': 'code',
        },
        follow_redirects=False,
    )
    assert response.status_code == HTTPStatus.FOUND
    location = response.headers['location']
    assert 'error=access_denied' in location
    assert 'state=xyz' in location

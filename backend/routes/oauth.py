# ruff: noqa: PLR0913, PLR0917
import asyncio
import secrets
from http import HTTPStatus
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from jwt import decode as jwt_decode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import User
from backend.core.oauth_models import OAuth2Client, OAuth2Token
from backend.core.schemas import OAuthClientCreate, OAuthClientCreatedResponse
from backend.database import get_session
from backend.security import get_password_hash
from backend.services.oauth_server import oauth_server
from backend.settings import Settings

router = APIRouter(prefix='/oauth', tags=['oauth'])
T_Session = Annotated[AsyncSession, Depends(get_session)]
_settings = Settings()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class OAuthRequestWrapper:
    def __init__(self, method, uri, form_data, headers=None):
        self.method = method
        self.uri = uri
        self.form_data = form_data
        self.headers = headers or {}


async def _get_client_or_400(client_id: str, session: AsyncSession):
    client = await session.scalar(
        select(OAuth2Client).where(OAuth2Client.client_id == client_id)
    )
    if not client:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='Unknown client_id',
        )
    return client


async def _user_from_cookie(
    access_token: str, session: AsyncSession
) -> User:
    try:
        payload = jwt_decode(
            access_token,
            _settings.SECRET_KEY,
            algorithms=[_settings.ALGORITHM],
        )
        email = payload.get('sub')
    except Exception:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail='Invalid token',
        )
    user = await session.scalar(select(User).where(User.email == email))
    if not user:
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)
    return user


# ---------------------------------------------------------------------------
# OAuth Client Registration
# ---------------------------------------------------------------------------

@router.post(
    '/clients',
    status_code=HTTPStatus.CREATED,
    response_model=OAuthClientCreatedResponse,
)
async def register_client(body: OAuthClientCreate, session: T_Session):
    client_id = secrets.token_hex(24)
    plaintext_secret = secrets.token_urlsafe(32)

    client = OAuth2Client(client_id=client_id)
    client.client_secret = get_password_hash(plaintext_secret)
    client.set_client_metadata({
        'client_name': body.client_name,
        'redirect_uris': body.redirect_uris,
        'scope': ' '.join(body.allowed_scopes),
        'response_types': ['code'],
        'grant_types': ['authorization_code', 'refresh_token'],
        'token_endpoint_auth_method': 'none',
    })

    session.add(client)
    await session.commit()

    return OAuthClientCreatedResponse(
        client_id=client_id,
        client_secret=plaintext_secret,
    )


# ---------------------------------------------------------------------------
# Authorization Endpoint
# ---------------------------------------------------------------------------

@router.get('/authorize')
async def authorize_get(
    request: Request,
    session: T_Session,
    client_id: str,
    redirect_uri: str,
    response_type: str = 'code',
    scope: str = 'openid',
    state: str = '',
    code_challenge: str = '',
    code_challenge_method: str = 'S256',
    access_token: str | None = Cookie(None),
):
    client = await _get_client_or_400(client_id, session)

    if redirect_uri not in client.redirect_uris:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='Invalid redirect_uri',
        )

    if not access_token:
        next_url = str(request.url)
        login_url = f'http://localhost:3000/login.html?next={next_url}'
        return RedirectResponse(login_url, status_code=HTTPStatus.FOUND)

    params = urlencode({
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': response_type,
        'scope': scope,
        'state': state,
        'code_challenge': code_challenge,
        'code_challenge_method': code_challenge_method,
        'client_name': client.client_name or client_id,
    })
    return RedirectResponse(
        f'http://localhost:3000/consent.html?{params}',
        status_code=HTTPStatus.FOUND,
    )


@router.post('/authorize')
async def authorize_post(
    request: Request,
    session: T_Session,
    access_token: str | None = Cookie(None),
):
    if not access_token:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail='Not authenticated',
        )

    form = await request.form()
    form_data = dict(form)

    action = form_data.get('action', 'allow')
    redirect_uri = form_data.get('redirect_uri', '')
    state = form_data.get('state', '')

    if action == 'deny':
        params = urlencode({'error': 'access_denied', 'state': state})
        return RedirectResponse(
            f'{redirect_uri}?{params}',
            status_code=HTTPStatus.FOUND,
        )

    user = await _user_from_cookie(access_token, session)

    if 'response_type' not in form_data:
        form_data['response_type'] = 'code'

    wrapper = OAuthRequestWrapper(
        method='POST',
        uri=str(request.url),
        form_data=form_data,
        headers=dict(request.headers),
    )

    status, body, headers = await asyncio.to_thread(
        oauth_server.create_authorization_response,
        wrapper,
        user,
    )

    headers_dict = dict(headers) if headers else {}
    location = headers_dict.get('Location') or headers_dict.get('location')
    if location:
        return RedirectResponse(location, status_code=HTTPStatus.FOUND)
    return JSONResponse(content=body, status_code=status)


# ---------------------------------------------------------------------------
# Token Endpoint
# ---------------------------------------------------------------------------

@router.post('/token')
async def token_endpoint(request: Request):
    form = await request.form()
    wrapper = OAuthRequestWrapper(
        method='POST',
        uri=str(request.url),
        form_data=dict(form),
        headers=dict(request.headers),
    )

    status, body, headers = await asyncio.to_thread(
        oauth_server.create_token_response,
        wrapper,
    )

    return JSONResponse(content=body, status_code=status)


# ---------------------------------------------------------------------------
# UserInfo Endpoint
# ---------------------------------------------------------------------------

@router.get('/userinfo')
async def userinfo(
    session: T_Session,
    authorization: str | None = Header(None),
):
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)

    token_str = authorization.removeprefix('Bearer ')
    token = await session.scalar(
        select(OAuth2Token).where(OAuth2Token.access_token == token_str)
    )

    if not token or token.is_expired() or token.is_revoked():
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)

    if 'openid' not in token.scope:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN)

    user = await session.scalar(
        select(User).where(User.id == token.user_id)
    )

    claims: dict = {'sub': str(user.id)}
    if 'email' in token.scope:
        claims['email'] = user.email
    if 'profile' in token.scope:
        claims['username'] = user.username

    return claims

# ruff: noqa: PLR6301
import secrets
import time

from authlib.oauth2 import AuthorizationServer
from authlib.oauth2.rfc6749.grants import (
    AuthorizationCodeGrant,
    RefreshTokenGrant,
)
from authlib.oauth2.rfc6749.requests import (
    BasicOAuth2Payload,
    JsonRequest,
    OAuth2Request,
)
from authlib.oauth2.rfc6750 import BearerTokenGenerator
from authlib.oauth2.rfc7636 import CodeChallenge
from authlib.oidc.core import UserInfo
from authlib.oidc.core.grants import OpenIDCode
from sqlalchemy import select

import backend.database as _db
from backend.core.models import User
from backend.core.oauth_models import (
    OAuth2AuthorizationCode,
    OAuth2Client,
    OAuth2Token,
)
from backend.settings import Settings

settings = Settings()


# ---------------------------------------------------------------------------
# Request adapter
# ---------------------------------------------------------------------------

class _AppOAuth2Request(OAuth2Request):
    """Exposes payload data via the legacy .form property."""

    @property
    def form(self):
        return self.payload.data if self.payload else {}

    @property
    def args(self):
        return {}


# ---------------------------------------------------------------------------
# Authorization Code Grant
# ---------------------------------------------------------------------------

class AuthCodeGrant(AuthorizationCodeGrant):
    AUTHORIZATION_CODE_LENGTH = 48
    TOKEN_ENDPOINT_AUTH_METHODS = [
        'client_secret_basic',
        'client_secret_post',
        'none',
    ]

    def save_authorization_code(self, code, request):
        with _db.SyncSession() as s:
            auth_code = OAuth2AuthorizationCode(
                code=code,
                client_id=request.payload.client_id,
                redirect_uri=request.payload.redirect_uri or '',
                scope=request.payload.scope or '',
                user_id=request.user.id,
                code_challenge=request.payload.data.get('code_challenge'),
                code_challenge_method=request.payload.data.get(
                    'code_challenge_method'
                ),
                nonce=request.payload.data.get('nonce'),
            )
            s.add(auth_code)
            s.commit()

    def query_authorization_code(self, code, client):
        with _db.SyncSession() as s:
            return s.scalar(
                select(OAuth2AuthorizationCode).where(
                    OAuth2AuthorizationCode.code == code,
                    OAuth2AuthorizationCode.client_id == client.client_id,
                )
            )

    def delete_authorization_code(self, authorization_code):
        with _db.SyncSession() as s:
            obj = s.get(OAuth2AuthorizationCode, authorization_code.id)
            if obj:
                s.delete(obj)
                s.commit()

    def authenticate_user(self, authorization_code):
        with _db.SyncSession() as s:
            return s.get(User, authorization_code.user_id)


# ---------------------------------------------------------------------------
# OIDC extension (registered as an extension, not a mixin)
# ---------------------------------------------------------------------------

class OIDCCodeExtension(OpenIDCode):
    def exists_nonce(self, nonce, request):
        with _db.SyncSession() as s:
            return bool(
                s.scalar(
                    select(OAuth2AuthorizationCode).where(
                        OAuth2AuthorizationCode.nonce == nonce,
                        OAuth2AuthorizationCode.client_id
                        == request.payload.client_id,
                    )
                )
            )

    def get_jwt_config(self, grant):
        return {
            'key': settings.SECRET_KEY,
            'alg': 'HS256',
            'iss': settings.BASE_URL,
            'exp': 3600,
        }

    def generate_user_info(self, user, scope):
        info = UserInfo(sub=str(user.id))
        if 'email' in scope:
            info['email'] = user.email
        if 'profile' in scope:
            info['username'] = user.username
        return info


# ---------------------------------------------------------------------------
# Refresh Token Grant
# ---------------------------------------------------------------------------

class AppRefreshTokenGrant(RefreshTokenGrant):
    TOKEN_ENDPOINT_AUTH_METHODS = [
        'client_secret_basic',
        'client_secret_post',
        'none',
    ]

    def authenticate_refresh_token(self, refresh_token):
        with _db.SyncSession() as s:
            token = s.scalar(
                select(OAuth2Token).where(
                    OAuth2Token.refresh_token == refresh_token
                )
            )
            if token and not token.is_expired() and not token.is_revoked():
                return token
            return None

    def authenticate_user(self, credential):
        with _db.SyncSession() as s:
            return s.get(User, credential.user_id)

    def revoke_old_credential(self, credential):
        with _db.SyncSession() as s:
            obj = s.get(OAuth2Token, credential.id)
            if obj:
                obj.access_token_revoked_at = int(time.time())
                obj.refresh_token_revoked_at = int(time.time())
                s.commit()


# ---------------------------------------------------------------------------
# Authorization Server
# ---------------------------------------------------------------------------

class FastAPIAuthorizationServer(AuthorizationServer):
    def create_oauth2_request(self, request):
        oauth_req = _AppOAuth2Request(
            method=request.method,
            uri=str(request.uri),
            headers=dict(request.headers),
        )
        oauth_req.payload = BasicOAuth2Payload(request.form_data)
        return oauth_req

    def create_json_request(self, request):
        return JsonRequest(
            method=request.method,
            uri=str(request.uri),
            headers=dict(request.headers),
        )

    def handle_response(self, status, body, headers):
        return status, body, headers

    def query_client(self, client_id):
        with _db.SyncSession() as s:
            return s.scalar(
                select(OAuth2Client).where(
                    OAuth2Client.client_id == client_id
                )
            )

    def save_token(self, token, request):
        with _db.SyncSession() as s:
            user_id = request.user.id if request.user else None
            item = OAuth2Token(
                client_id=request.payload.client_id,
                user_id=user_id,
                **token,
            )
            s.add(item)
            s.commit()

    def send_signal(self, name, *args, **kwargs):
        pass


# ---------------------------------------------------------------------------
# Configured instance
# ---------------------------------------------------------------------------

oauth_server = FastAPIAuthorizationServer(
    scopes_supported=['openid', 'email', 'profile']
)
oauth_server.register_grant(
    AuthCodeGrant,
    [CodeChallenge(required=True), OIDCCodeExtension()],
)
oauth_server.register_grant(AppRefreshTokenGrant)
oauth_server.register_token_generator(
    'default',
    BearerTokenGenerator(
        access_token_generator=lambda **_kw: secrets.token_urlsafe(48),
        refresh_token_generator=lambda **_kw: secrets.token_urlsafe(48),
        expires_generator=lambda grant_type, client: 3600,
    ),
)

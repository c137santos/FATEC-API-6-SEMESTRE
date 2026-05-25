import base64
import hashlib
from types import SimpleNamespace

from authlib.oauth2 import AuthorizationServer
from authlib.oauth2.rfc6749.grants import (
    AuthorizationCodeGrant,
    RefreshTokenGrant,
)
from authlib.oauth2.rfc7636 import CodeChallenge

from backend.services.oauth_server import (
    AuthCodeGrant,
    OIDCCodeExtension,
    oauth_server,
)


def test_oauth_server_is_configured():
    assert isinstance(oauth_server, AuthorizationServer)


def test_authorization_code_grant_is_registered():
    grant_classes = [g for g, _ in oauth_server._authorization_grants]
    assert any(issubclass(g, AuthorizationCodeGrant) for g in grant_classes)


def test_refresh_token_grant_is_registered():
    grant_classes = [g for g, _ in oauth_server._token_grants]
    assert any(issubclass(g, RefreshTokenGrant) for g in grant_classes)


# ---------------------------------------------------------------------------
# generate_user_info scope tests (no DB required)
# ---------------------------------------------------------------------------

def _fake_user():
    return SimpleNamespace(id=42, email='user@example.com', username='alice')


def test_user_info_openid_scope_returns_sub_only():
    grant = OIDCCodeExtension.__new__(OIDCCodeExtension)
    user = _fake_user()
    info = grant.generate_user_info(user, 'openid')
    assert info['sub'] == '42'
    assert 'email' not in info
    assert 'username' not in info


def test_user_info_email_scope_adds_email():
    grant = OIDCCodeExtension.__new__(OIDCCodeExtension)
    user = _fake_user()
    info = grant.generate_user_info(user, 'openid email')
    assert info['sub'] == '42'
    assert info['email'] == 'user@example.com'
    assert 'username' not in info


def test_user_info_profile_scope_adds_username():
    grant = OIDCCodeExtension.__new__(OIDCCodeExtension)
    user = _fake_user()
    info = grant.generate_user_info(user, 'openid profile')
    assert info['sub'] == '42'
    assert info['username'] == 'alice'
    assert 'email' not in info


# ---------------------------------------------------------------------------
# PKCE S256 validation (no DB required)
# ---------------------------------------------------------------------------

def _s256_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode()


def test_pkce_correct_s256_verifier_passes():
    verifier = 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk'
    challenge = _s256_challenge(verifier)
    s256_fn = CodeChallenge.CODE_CHALLENGE_METHODS['S256']
    assert s256_fn(verifier, challenge) is True


def test_pkce_wrong_verifier_fails():
    verifier = 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk'
    challenge = _s256_challenge(verifier)
    s256_fn = CodeChallenge.CODE_CHALLENGE_METHODS['S256']
    wrong = 'wrong-verifier-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
    assert s256_fn(wrong, challenge) is False


def test_pkce_s256_is_supported():
    assert 'S256' in CodeChallenge.SUPPORTED_CODE_CHALLENGE_METHOD

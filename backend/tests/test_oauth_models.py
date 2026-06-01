
from freezegun import freeze_time
from sqlalchemy import select

from backend.core.oauth_models import (
    OAuth2AuthorizationCode,
    OAuth2Client,
    OAuth2Token,
)


async def test_oauth2client_lookup_by_client_id(session):
    client = OAuth2Client(client_id='app-123')
    session.add(client)
    await session.commit()

    result = await session.scalar(
        select(OAuth2Client).where(OAuth2Client.client_id == 'app-123')
    )
    assert result is not None
    assert result.client_id == 'app-123'


async def test_oauth2client_stores_metadata(session):
    client = OAuth2Client(client_id='app-meta')
    client.set_client_metadata({
        'client_name': 'My App',
        'redirect_uris': ['http://localhost/callback'],
        'scope': 'openid email profile',
    })
    session.add(client)
    await session.commit()
    await session.refresh(client)

    assert client.client_name == 'My App'
    assert 'http://localhost/callback' in client.redirect_uris
    assert client.get_allowed_scope('openid email') == 'openid email'


async def test_auth_code_stores_pkce_and_user_id(session, user):
    code = OAuth2AuthorizationCode(
        code='testcode',
        client_id='app-123',
        user_id=user.id,
        code_challenge='challenge_value',
        code_challenge_method='S256',
        scope='openid',
    )
    session.add(code)
    await session.commit()

    result = await session.scalar(
        select(OAuth2AuthorizationCode).where(
            OAuth2AuthorizationCode.code == 'testcode'
        )
    )
    assert result.user_id == user.id
    assert result.code_challenge == 'challenge_value'
    assert result.code_challenge_method == 'S256'


async def test_auth_code_expires_after_60_seconds(session, user):
    with freeze_time('2024-01-01 12:00:00'):
        code = OAuth2AuthorizationCode(
            code='expiring-code',
            client_id='app-123',
            user_id=user.id,
            scope='openid',
        )
        session.add(code)
        await session.commit()
        await session.refresh(code)
        assert not code.is_expired()

    with freeze_time('2024-01-01 12:00:59'):
        assert not code.is_expired()

    with freeze_time('2024-01-01 12:01:01'):
        assert code.is_expired()


async def test_token_stores_access_and_refresh(session, user):
    token = OAuth2Token(
        client_id='app-123',
        user_id=user.id,
        access_token='access-abc',
        refresh_token='refresh-xyz',
        scope='openid email',
        token_type='Bearer',
        expires_in=3600,
    )
    session.add(token)
    await session.commit()

    result = await session.scalar(
        select(OAuth2Token).where(OAuth2Token.access_token == 'access-abc')
    )
    assert result.user_id == user.id
    assert result.client_id == 'app-123'
    assert result.refresh_token == 'refresh-xyz'
    assert result.get_scope() == 'openid email'


async def test_token_is_expired_after_expires_in(session, user):
    with freeze_time('2024-01-01 12:00:00'):
        token = OAuth2Token(
            client_id='app-123',
            user_id=user.id,
            access_token='access-expiring',
            token_type='Bearer',
            scope='openid',
            expires_in=300,
        )
        session.add(token)
        await session.commit()
        await session.refresh(token)
        assert not token.is_expired()

    with freeze_time('2024-01-01 12:04:59'):
        assert not token.is_expired()

    with freeze_time('2024-01-01 12:05:01'):
        assert token.is_expired()

import secrets
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

from backend.core.schemas import UserPublic


async def test_get_me_returns_current_user(client, user, token):
    response = await client.get(
        '/users/me',
        cookies={'access_token': token},
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['email'] == user.email
    assert data['username'] == user.username


async def test_get_me_without_cookie_returns_401(client):
    response = await client.get('/users/me')
    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_registration_without_consent_returns_400(client):
    response = await client.post(
        '/users/',
        json={
            'username': 'testeusername',
            'email': 'teste@teste.com',
            'password': 'password',
            'consented': False,
        },
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json() == {'detail': 'Consent is required'}


async def test_create_user(client, consent_policy):
    with patch('backend.routes.users.send_confirmation_email', new_callable=AsyncMock):
        response = await client.post(
            '/users/',
            json={
                'username': 'testeusername',
                'email': 'teste@teste.com',
                'password': 'password',
                'consented': True,
            },
        )

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data['username'] == 'testeusername'
    assert data['email'] == 'teste@teste.com'
    assert 'id' in data
    assert data['consented_at'] is not None
    assert data['consent_policy_id'] == consent_policy.id


async def test_read_users(client, user):
    user_schema = UserPublic.model_validate(user).model_dump()
    response = await client.get(f'/users/?skip=0&limit=1000')

    assert response.status_code == HTTPStatus.OK
    assert user_schema in response.json()['users']


async def test_update_user(client, user, token):
    response = await client.put(
        f'/users/{user.id}',
        cookies={'access_token': token},
        json={
            'username': 'testeusername2',
            'email': 'test@test.com',
            'password': '123',
        },
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['username'] == 'testeusername2'
    assert data['email'] == 'test@test.com'
    assert data['id'] == user.id


async def test_delete_user(client, user, token):
    response = await client.delete(
        f'/users/{user.id}',
        cookies={'access_token': token},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': 'User deleted'}


async def test_delete_wrong_user(client, other_user, token):
    response = await client.delete(
        f'/users/{other_user.id}',
        cookies={'access_token': token},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {'detail': 'Not enough permission'}


async def test_verify_email_with_valid_token(client, session, unverified_user):
    token = secrets.token_urlsafe(32)
    unverified_user.email_token = token
    unverified_user.email_token_expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=24)
    await session.commit()

    response = await client.get(f'/users/verify-email?token={token}')

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': 'Email confirmado com sucesso'}

    await session.refresh(unverified_user)
    assert unverified_user.is_verified is True
    assert unverified_user.email_token is None


async def test_verify_email_with_expired_token(client, session, unverified_user):
    token = secrets.token_urlsafe(32)
    unverified_user.email_token = token
    unverified_user.email_token_expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
    await session.commit()

    response = await client.get(f'/users/verify-email?token={token}')

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json() == {'detail': 'Token expirado'}


async def test_verify_email_with_invalid_token(client):
    response = await client.get('/users/verify-email?token=token-que-nao-existe')

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json() == {'detail': 'Token inválido'}


async def test_registration_sends_confirmation_email(client, consent_policy):
    with patch('backend.routes.users.send_confirmation_email', new_callable=AsyncMock) as mock_send:
        response = await client.post(
            '/users/',
            json={
                'username': 'newuser',
                'email': 'newuser@test.com',
                'password': 'password',
                'consented': True,
            },
        )

    assert response.status_code == HTTPStatus.CREATED
    mock_send.assert_called_once()
    call_args = mock_send.call_args
    assert call_args.args[0] == 'newuser@test.com'


async def test_registration_succeeds_even_if_smtp_fails(client, consent_policy):
    with patch('backend.routes.users.send_confirmation_email', new_callable=AsyncMock) as mock_send:
        mock_send.side_effect = Exception('SMTP unavailable')
        response = await client.post(
            '/users/',
            json={
                'username': 'smtpfailuser',
                'email': 'smtpfail@test.com',
                'password': 'password',
                'consented': True,
            },
        )

    assert response.status_code == HTTPStatus.CREATED


async def test_registered_user_is_unverified(client, session, consent_policy):
    with patch('backend.routes.users.send_confirmation_email', new_callable=AsyncMock):
        response = await client.post(
            '/users/',
            json={
                'username': 'unverifiedreg',
                'email': 'unverifiedreg@test.com',
                'password': 'password',
                'consented': True,
            },
        )

    assert response.status_code == HTTPStatus.CREATED
    user_id = response.json()['id']

    from sqlalchemy import Select as Sel
    from backend.core.models import User as UserModel
    user = await session.scalar(Sel(UserModel).where(UserModel.id == user_id))
    assert user.is_verified is False
    assert user.email_token is not None


async def test_resend_verification_sends_new_email(client, session, unverified_user):
    old_token = secrets.token_urlsafe(32)
    unverified_user.email_token = old_token
    unverified_user.email_token_expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=24)
    await session.commit()

    with patch('backend.routes.users.send_confirmation_email', new_callable=AsyncMock) as mock_send:
        response = await client.post(
            '/users/resend-verification',
            json={'email': unverified_user.email},
        )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': 'Email de confirmação reenviado'}
    mock_send.assert_called_once()

    await session.refresh(unverified_user)
    assert unverified_user.email_token != old_token


async def test_resend_verification_unknown_email_returns_200(client):
    with patch('backend.routes.users.send_confirmation_email', new_callable=AsyncMock):
        response = await client.post(
            '/users/resend-verification',
            json={'email': 'nobody@nowhere.com'},
        )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': 'Email de confirmação reenviado'}


async def test_update_user_with_wrong_user(client, other_user, token):
    response = await client.put(
        f'/users/{other_user.id}',
        cookies={'access_token': token},
        json={
            'username': 'bob',
            'email': 'bob@example.com',
            'password': 'mynewpassword',
        },
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {'detail': 'Not enough permission'}

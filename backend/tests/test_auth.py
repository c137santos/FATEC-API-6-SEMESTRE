from http import HTTPStatus
from freezegun import freeze_time


async def test_login_sets_httponly_cookie(client, user):
    response = await client.post(
        '/auth/token',
        data={'username': user.email, 'password': user.clean_password},
    )
    assert response.status_code == HTTPStatus.OK
    set_cookie = response.headers.get('set-cookie', '')
    assert 'access_token=' in set_cookie
    assert 'HttpOnly' in set_cookie
    assert 'samesite=lax' in set_cookie.lower()


async def test_login_body_has_no_access_token(client, user):
    response = await client.post(
        '/auth/token',
        data={'username': user.email, 'password': user.clean_password},
    )
    assert response.status_code == HTTPStatus.OK
    assert 'access_token' not in response.json()
    assert response.json()['token_type'] == 'bearer'


async def test_protected_route_without_cookie_returns_401(client, user):
    response = await client.delete(f'/users/{user.id}')
    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_protected_route_with_cookie_succeeds(client, user):
    await client.post(
        '/auth/token',
        data={'username': user.email, 'password': user.clean_password},
    )
    response = await client.delete(f'/users/{user.id}')
    assert response.status_code == HTTPStatus.OK


async def test_refresh_sets_new_cookie(client, user):
    await client.post(
        '/auth/token',
        data={'username': user.email, 'password': user.clean_password},
    )
    response = await client.post('/auth/refresh_token')
    assert response.status_code == HTTPStatus.OK
    set_cookie = response.headers.get('set-cookie', '')
    assert 'access_token=' in set_cookie
    assert 'HttpOnly' in set_cookie


async def test_refresh_without_cookie_returns_401(client):
    response = await client.post('/auth/refresh_token')
    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_expired_cookie_returns_401_on_protected_route(client, user):
    with freeze_time('2023-07-14 12:00:00'):
        await client.post(
            '/auth/token',
            data={'username': user.email, 'password': user.clean_password},
        )
    with freeze_time('2023-07-14 12:31:00'):
        response = await client.put(
            f'/users/{user.id}',
            json={'username': 'x', 'email': 'x@x.com', 'password': 'x'},
        )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Could not validate credentials'}


async def test_expired_cookie_cannot_refresh(client, user):
    with freeze_time('2023-07-14 12:00:00'):
        await client.post(
            '/auth/token',
            data={'username': user.email, 'password': user.clean_password},
        )
    with freeze_time('2023-07-14 12:31:00'):
        response = await client.post('/auth/refresh_token')
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Could not validate credentials'}


async def test_logout_clears_cookie(client, user):
    await client.post(
        '/auth/token',
        data={'username': user.email, 'password': user.clean_password},
    )
    response = await client.post('/auth/logout')
    assert response.status_code == HTTPStatus.OK
    set_cookie = response.headers.get('set-cookie', '')
    assert 'access_token=' in set_cookie
    assert 'max-age=0' in set_cookie.lower()


async def test_token_wrong_password(client, user):
    response = await client.post(
        '/auth/token',
        data={'username': user.email, 'password': 'wrong_password'},
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json() == {'detail': 'Incorrect email or password'}


async def test_token_wrong_email(client, user):
    response = await client.post(
        '/auth/token',
        data={'username': 'nhe@nhe.com', 'password': user.clean_password},
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json() == {'detail': 'Incorrect email or password'}



async def test_login_blocked_for_unverified_user(client, unverified_user):
    response = await client.post(
        '/auth/token',
        data={'username': unverified_user.email, 'password': unverified_user.clean_password},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {'detail': 'Email não confirmado'}

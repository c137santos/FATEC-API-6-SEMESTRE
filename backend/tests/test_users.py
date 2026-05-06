from http import HTTPStatus

from backend.core.schemas import UserPublic


async def test_create_user(client):
    response = await client.post(
        '/users/',
        json={
            'username': 'testeusername',
            'email': 'teste@teste.com',
            'password': 'password',
        },
    )

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data['username'] == 'testeusername'
    assert data['email'] == 'teste@teste.com'
    assert 'id' in data


async def test_read_users(client, user):
    user_schema = UserPublic.model_validate(user).model_dump()
    response = await client.get('/users/')

    assert response.status_code == HTTPStatus.OK
    assert user_schema in response.json()['users']


async def test_update_user(client, user, token):
    response = await client.put(
        f'/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
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
        headers={'Authorization': f'Bearer {token}'},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'message': 'User deleted'}


async def test_delete_wrong_user(client, other_user, token):
    response = await client.delete(
        f'/users/{other_user.id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {'detail': 'Not enough permission'}


async def test_update_user_with_wrong_user(client, other_user, token):
    response = await client.put(
        f'/users/{other_user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'username': 'bob',
            'email': 'bob@example.com',
            'password': 'mynewpassword',
        },
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {'detail': 'Not enough permission'}

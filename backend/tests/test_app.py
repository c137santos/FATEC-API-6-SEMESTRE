from http import HTTPStatus


async def test_root_deve_retornar_ok(client):
    response = await client.get('/')

    assert response.status_code == HTTPStatus.OK

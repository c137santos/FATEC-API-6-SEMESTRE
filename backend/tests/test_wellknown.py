from http import HTTPStatus


async def test_openid_configuration_returns_200_json(client):
    response = await client.get('/.well-known/openid-configuration')
    assert response.status_code == HTTPStatus.OK
    assert 'application/json' in response.headers['content-type']


async def test_openid_configuration_has_required_fields(client):
    response = await client.get('/.well-known/openid-configuration')
    doc = response.json()

    required_fields = [
        'issuer',
        'authorization_endpoint',
        'token_endpoint',
        'userinfo_endpoint',
        'scopes_supported',
        'response_types_supported',
        'id_token_signing_alg_values_supported',
    ]
    for field in required_fields:
        assert field in doc, f'Missing field: {field}'


async def test_url_fields_are_absolute(client):
    response = await client.get('/.well-known/openid-configuration')
    doc = response.json()

    url_fields = [
        'issuer',
        'authorization_endpoint',
        'token_endpoint',
        'userinfo_endpoint',
    ]
    for field in url_fields:
        assert doc[field].startswith('http'), f'{field} is not an absolute URL'


async def test_fixed_values_match_spec(client):
    response = await client.get('/.well-known/openid-configuration')
    doc = response.json()

    assert doc['scopes_supported'] == ['openid', 'email', 'profile']
    assert doc['response_types_supported'] == ['code']
    assert doc['id_token_signing_alg_values_supported'] == ['HS256']

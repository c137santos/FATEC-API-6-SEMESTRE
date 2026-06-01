from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.settings import Settings

router = APIRouter(prefix='/.well-known', tags=['oidc'])
settings = Settings()


@router.get('/openid-configuration')
def openid_configuration():
    base = settings.BASE_URL.rstrip('/')
    return JSONResponse({
        'issuer': base,
        'authorization_endpoint': f'{base}/oauth/authorize',
        'token_endpoint': f'{base}/oauth/token',
        'userinfo_endpoint': f'{base}/oauth/userinfo',
        'scopes_supported': ['openid', 'email', 'profile'],
        'response_types_supported': ['code'],
        'id_token_signing_alg_values_supported': ['HS256'],
    })

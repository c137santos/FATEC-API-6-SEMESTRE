import logging

import httpx

from backend.core.utils import normalize_cnpj

logger = logging.getLogger(__name__)

ANEEL_DATASTORE_URL = (
    'https://dadosabertos.aneel.gov.br/api/3/action/datastore_search'
)
ANEEL_RESOURCE_ID = '4493985c-baea-429c-9df5-3030422c71d7'
_ANEEL_FIELDS = 'DatGeracaoConjuntoDados,SigAgente,NumCNPJ'
_PAGE_SIZE = 100


async def fetch_aneel_cnpj_map(
    client: httpx.AsyncClient | None = None,
) -> dict[str, str]:
    """Fetch all SigAgente->CNPJ pairs from ANEEL open-data API.

    Returns a dict keyed by SigAgente (original case) mapped to a
    14-digit normalized CNPJ string. Raises httpx.HTTPError on failure.
    """
    result: dict[str, str] = {}
    offset = 0

    async def _get(c: httpx.AsyncClient) -> None:
        nonlocal offset
        while True:
            resp = await c.get(
                ANEEL_DATASTORE_URL,
                params={
                    'resource_id': ANEEL_RESOURCE_ID,
                    'limit': _PAGE_SIZE,
                    'offset': offset,
                    'fields': _ANEEL_FIELDS,
                    'distinct': 'true',
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            payload = resp.json()
            api_result = payload.get('result', {})
            records = api_result.get('records', [])

            if not records:
                break

            for record in records:
                sig = record.get('SigAgente')
                cnpj_raw = record.get('NumCNPJ')
                if sig and cnpj_raw:
                    try:
                        result[sig.strip()] = normalize_cnpj(str(cnpj_raw))
                    except ValueError:
                        logger.warning(
                            'CNPJ inválido para %s: %r', sig, cnpj_raw
                        )

            offset += len(records)
            total = api_result.get('total', 0)
            if offset >= total:
                break

    try:
        if client is not None:
            await _get(client)
        else:
            async with httpx.AsyncClient() as managed:
                await _get(managed)
    except httpx.HTTPError as exc:
        logger.error('Falha ao consultar API ANEEL: %s', exc)
        raise

    return result

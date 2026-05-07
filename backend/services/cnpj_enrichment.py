import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import Distribuidora

logger = logging.getLogger(__name__)


async def enrich_distribuidoras(
    session: AsyncSession,
    aneel_map: dict[str, str],
) -> dict[str, int]:
    """Exact-match distribuidoras (status IS NULL) against the ANEEL map.

    Updates matched rows with cnpj/cnpj_match/cnpj_source/cnpj_enrichment_status.
    Marks unmatched rows as 'no_match'.
    Rows already 'matched' or 'no_match' are skipped.

    Returns counts: {'matched': N, 'no_match': M}.
    """
    stmt = select(Distribuidora).where(
        Distribuidora.cnpj_enrichment_status.is_(None)
    )
    rows = (await session.execute(stmt)).scalars().all()

    lower_map = {k.lower(): (k, v) for k, v in aneel_map.items()}

    matched = 0
    no_match = 0

    for dist in rows:
        key = dist.dist_name.lower()
        if key in lower_map:
            _, cnpj = lower_map[key]
            await session.execute(
                update(Distribuidora)
                .where(
                    Distribuidora.id == dist.id,
                    Distribuidora.date_gdb == dist.date_gdb,
                )
                .values(
                    cnpj=cnpj,
                    cnpj_match=1.0,
                    cnpj_source='aneel_api',
                    cnpj_enrichment_status='matched',
                )
            )
            matched += 1
        else:
            await session.execute(
                update(Distribuidora)
                .where(
                    Distribuidora.id == dist.id,
                    Distribuidora.date_gdb == dist.date_gdb,
                )
                .values(cnpj_enrichment_status='no_match')
            )
            no_match += 1

    await session.commit()
    logger.info('CNPJ enrichment: matched=%d no_match=%d', matched, no_match)
    return {'matched': matched, 'no_match': no_match}

import logging
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase
from rapidfuzz import fuzz, process
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import Distribuidora, DistribuidoraCnpj

logger = logging.getLogger(__name__)

_FUZZY_THRESHOLD = 95.0  # score is 0–100


async def enrich_distribuidoras(
    session: AsyncSession,
    aneel_map: dict[str, str],
    mongo_db: AsyncIOMotorDatabase | None = None,
) -> dict[str, int]:
    """Exact-match then fuzzy-match pending distribuidoras against the ANEEL map.

    Distribuidoras without a row in distribuidora_cnpj are processed:
    - Exact match (case-insensitive): inserts 'matched', cnpj_match=1.0
    - Fuzzy match ≥ 95%: inserts 'matched', cnpj_match=<score>
    - Fuzzy match < 95%: logs to cnpj_enrichment_log (MongoDB), inserts 'no_match'
    One row is written per unique dist_id regardless of how many years it appears.

    Returns {'matched': N, 'no_match': M, 'pending': P} where pending is the
    count of distinct distribuidoras still without a cnpj row after the run.
    """
    already_enriched = select(DistribuidoraCnpj.dist_id)
    stmt = (
        select(Distribuidora.id, func.min(Distribuidora.dist_name).label('dist_name'))
        .where(Distribuidora.id.not_in(already_enriched))
        .group_by(Distribuidora.id)
    )
    rows = (await session.execute(stmt)).all()

    lower_map = {k.lower(): (k, v) for k, v in aneel_map.items()}
    aneel_keys = list(aneel_map.keys())

    matched = 0
    no_match = 0

    for dist_id, dist_name in rows:
        key = dist_name.lower()

        if key in lower_map:
            _, cnpj = lower_map[key]
            await session.execute(
                insert(DistribuidoraCnpj)
                .values(
                    dist_id=dist_id,
                    cnpj=cnpj,
                    cnpj_match=1.0,
                    cnpj_source='aneel_api',
                    cnpj_enrichment_status='matched',
                )
                .on_conflict_do_nothing()
            )
            matched += 1
            continue

        best = (
            process.extractOne(dist_name, aneel_keys, scorer=fuzz.WRatio)
            if aneel_keys
            else None
        )

        if best is not None and best[1] >= _FUZZY_THRESHOLD:
            best_key, score, _ = best
            cnpj = aneel_map[best_key]
            await session.execute(
                insert(DistribuidoraCnpj)
                .values(
                    dist_id=dist_id,
                    cnpj=cnpj,
                    cnpj_match=round(score / 100.0, 4),
                    cnpj_source='aneel_api',
                    cnpj_enrichment_status='matched',
                )
                .on_conflict_do_nothing()
            )
            matched += 1
        else:
            best_key, score = (best[0], best[1]) if best is not None else (None, 0)
            if mongo_db is not None:
                await mongo_db['cnpj_enrichment_log'].insert_one(
                    {
                        'dist_id': dist_id,
                        'dist_name': dist_name,
                        'aneel_sig_agente': best_key,
                        'aneel_cnpj': aneel_map[best_key] if best_key else None,
                        'match_score': round(score / 100.0, 4),
                        'attempted_at': datetime.utcnow(),
                    }
                )
            await session.execute(
                insert(DistribuidoraCnpj)
                .values(
                    dist_id=dist_id,
                    cnpj_enrichment_status='no_match',
                    cnpj_match=round(score / 100.0, 4),
                )
                .on_conflict_do_nothing()
            )
            no_match += 1

    await session.commit()

    pending_count = (
        await session.execute(
            select(func.count(func.distinct(Distribuidora.id))).where(
                Distribuidora.id.not_in(select(DistribuidoraCnpj.dist_id))
            )
        )
    ).scalar_one()

    logger.info(
        'CNPJ enrichment: matched=%d no_match=%d pending=%d',
        matched,
        no_match,
        pending_count,
    )
    return {'matched': matched, 'no_match': no_match, 'pending': int(pending_count)}

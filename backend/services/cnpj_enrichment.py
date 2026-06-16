import logging
import unicodedata
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase
from rapidfuzz import fuzz, process
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

import httpx

from backend.clients.aneel import fetch_aneel_cnpj_map
from backend.core.models import Distribuidora, DistribuidoraCnpj

logger = logging.getLogger(__name__)

_FUZZY_THRESHOLD = 95.0  # score is 0–100


def _norm(s: str) -> str:
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.lower().replace('_', ' ').replace('-', ' ')


async def _build_sig_agente_map_from_mongo(
    mongo_db: AsyncIOMotorDatabase,
) -> dict[str, str]:
    """Build sig_agente -> cnpj map from dec_fec_realizado collection."""
    result: dict[str, str] = {}
    pipeline = [
        {'$match': {'sig_agente': {'$ne': None}, 'num_cnpj': {'$ne': None}}},
        {'$group': {'_id': '$sig_agente', 'cnpj': {'$first': '$num_cnpj'}}},
    ]
    async for doc in mongo_db['dec_fec_realizado'].aggregate(pipeline):
        sig = doc.get('_id')
        cnpj = doc.get('cnpj')
        if sig and cnpj:
            result[sig.strip()] = cnpj
    return result


async def enrich_distribuidoras(
    session: AsyncSession,
    mongo_db: AsyncIOMotorDatabase,
) -> dict[str, int]:
    """Match dist_name from PostgreSQL against ANEEL API, falling back to MongoDB.

    For each distribuidora pending CNPJ enrichment:
    1. Try ANEEL open-data API (fetch_aneel_cnpj_map). If the API is unavailable
       the map is treated as empty and all records fall through to step 2.
    2. For records without a match from ANEEL, try dec_fec_realizado (MongoDB).
    - Exact match (case-insensitive): inserts 'matched', cnpj_match=1.0
    - Fuzzy match >= 95%: inserts 'matched', cnpj_match=<score>
    - No match after both passes: logs to cnpj_enrichment_log, inserts 'no_match'
    One row is written per unique dist_id regardless of how many years it appears.

    Returns {'matched': N, 'no_match': M, 'pending': P}.
    """
    try:
        aneel_map = await fetch_aneel_cnpj_map()
    except httpx.HTTPError as exc:
        logger.warning('ANEEL API indisponível, usando apenas fallback mongo: %s', exc)
        aneel_map = {}

    already_enriched = select(DistribuidoraCnpj.dist_id)
    stmt = (
        select(
            Distribuidora.id,
            func.min(Distribuidora.dist_name).label('dist_name'),
        )
        .where(Distribuidora.id.not_in(already_enriched))
        .group_by(Distribuidora.id)
    )
    rows = (await session.execute(stmt)).all()

    aneel_lower = {_norm(k): (k, v) for k, v in aneel_map.items()}
    aneel_norm_keys = list(aneel_lower.keys())

    matched = 0
    no_match = 0
    unmatched: list[tuple[int, str]] = []

    # Pass 1: ANEEL
    for dist_id, dist_name in rows:
        key = _norm(dist_name)

        if key in aneel_lower:
            _, cnpj = aneel_lower[key]
            await session.execute(
                insert(DistribuidoraCnpj)
                .values(
                    dist_id=dist_id,
                    cnpj=cnpj,
                    cnpj_match=1.0,
                    cnpj_source='aneel',
                    cnpj_enrichment_status='matched',
                )
                .on_conflict_do_nothing()
            )
            matched += 1
            continue

        best = (
            process.extractOne(key, aneel_norm_keys, scorer=fuzz.WRatio)
            if aneel_norm_keys
            else None
        )

        if best is not None and best[1] >= _FUZZY_THRESHOLD:
            best_norm_key, score, _ = best
            _, cnpj = aneel_lower[best_norm_key]
            await session.execute(
                insert(DistribuidoraCnpj)
                .values(
                    dist_id=dist_id,
                    cnpj=cnpj,
                    cnpj_match=round(score / 100.0, 4),
                    cnpj_source='aneel',
                    cnpj_enrichment_status='matched',
                )
                .on_conflict_do_nothing()
            )
            matched += 1
        else:
            aneel_score = best[1] if best is not None else 0.0
            unmatched.append((dist_id, dist_name, aneel_score))

    # Pass 2: MongoDB fallback for records without ANEEL match
    if unmatched:
        sig_agente_map = await _build_sig_agente_map_from_mongo(mongo_db)
        lower_map = {_norm(k): (k, v) for k, v in sig_agente_map.items()}
        norm_keys = list(lower_map.keys())

        for dist_id, dist_name, aneel_score in unmatched:
            key = _norm(dist_name)

            if key in lower_map:
                _, cnpj = lower_map[key]
                await session.execute(
                    insert(DistribuidoraCnpj)
                    .values(
                        dist_id=dist_id,
                        cnpj=cnpj,
                        cnpj_match=1.0,
                        cnpj_source='dec_fec',
                        cnpj_enrichment_status='matched',
                    )
                    .on_conflict_do_nothing()
                )
                matched += 1
                continue

            best = (
                process.extractOne(key, norm_keys, scorer=fuzz.WRatio)
                if norm_keys
                else None
            )

            if best is not None and best[1] >= _FUZZY_THRESHOLD:
                best_norm_key, score, _ = best
                _, cnpj = lower_map[best_norm_key]
                await session.execute(
                    insert(DistribuidoraCnpj)
                    .values(
                        dist_id=dist_id,
                        cnpj=cnpj,
                        cnpj_match=round(score / 100.0, 4),
                        cnpj_source='dec_fec',
                        cnpj_enrichment_status='matched',
                    )
                    .on_conflict_do_nothing()
                )
                matched += 1
            else:
                mongo_score = best[1] if best is not None else 0.0
                best_norm_key = best[0] if best is not None else None
                orig_key, orig_cnpj = (
                    lower_map[best_norm_key] if best_norm_key else (None, None)
                )
                best_score = max(aneel_score, mongo_score)
                await mongo_db['cnpj_enrichment_log'].insert_one({
                    'dist_id': dist_id,
                    'dist_name': dist_name,
                    'mongo_sig_agente': orig_key,
                    'mongo_cnpj': orig_cnpj,
                    'match_score': round(best_score / 100.0, 4),
                    'attempted_at': datetime.utcnow(),
                })
                await session.execute(
                    insert(DistribuidoraCnpj)
                    .values(
                        dist_id=dist_id,
                        cnpj_enrichment_status='no_match',
                        cnpj_match=round(best_score / 100.0, 4),
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
    return {
        'matched': matched,
        'no_match': no_match,
        'pending': int(pending_count),
    }

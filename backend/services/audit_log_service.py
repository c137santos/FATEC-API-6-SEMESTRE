"""
Audit log helper — append-only, sem UPDATE ou DELETE.

Uso:
    from backend.core.audit_log import Operation
    from backend.services.audit_log_service import write_log

    await write_log(
        operation=Operation.ACCOUNT_UPDATED,
        user_id=user.id,
        entity_name="User",
        from_value={"username": "antigo"},
        to_value={"username": "novo"},
    )
"""

import logging
from datetime import datetime, UTC
from typing import Any

from backend.core.audit_log import AUDIT_LOG_COLLECTION, Operation, _sanitize
from backend.database import get_mongo_async_db

logger = logging.getLogger(__name__)


async def write_log(
    operation: Operation,
    user_id: str | int,
    entity_name: str = "",
    from_value: dict[str, Any] | None = None,
    to_value: dict[str, Any] | None = None,
) -> None:
    """Grava um evento de auditoria imutável no MongoDB.

    Os campos `from_value` e `to_value` são sanitizados automaticamente
    para remover qualquer dado pessoal (PII) antes de persistir.
    """
    doc = {
        "user_id": str(user_id),
        "timestamp": datetime.now(UTC).replace(tzinfo=None),
        "operation": operation.value,
        "entity_name": entity_name,
        "from_value": _sanitize(from_value),
        "to_value": _sanitize(to_value),
    }
    try:
        db = get_mongo_async_db()
        await db[AUDIT_LOG_COLLECTION].insert_one(doc)
    except Exception:
        logger.exception(
            "Falha ao gravar audit log: op=%s entity=%s user=%s",
            operation.value, entity_name, user_id,
        )

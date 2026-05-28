"""
Script de contenção de incidente de segurança — Thunderstone

Execução (dentro do container):
    docker-compose exec api python docs/security/scripts/contain.py

O que faz:
    1. Revoga todos os tokens OAuth2 ativos
    2. Invalida todos os authorization codes pendentes
    3. Limpa email_token de todos os usuários
    4. Registra a contenção no audit log (MongoDB)
    5. Imprime próximos passos
"""

import sys
from datetime import datetime, UTC

from sqlalchemy import text

from backend.database import SyncSession, get_mongo_sync_db
from backend.core.audit_log import AUDIT_LOG_COLLECTION


def main() -> None:
    print(f"\n[{datetime.now(UTC).isoformat()}] Iniciando contenção de incidente...\n")

    with SyncSession() as session:
        result = session.execute(
            text("UPDATE oauth2_tokens SET revoked = true WHERE revoked = false")
        )
        tokens_revogados = result.rowcount
        print(f"  [OK] Tokens OAuth2 revogados: {tokens_revogados}")

        result = session.execute(text("DELETE FROM oauth2_authorization_codes"))
        codes_removidos = result.rowcount
        print(f"  [OK] Authorization codes removidos: {codes_removidos}")

        result = session.execute(
            text(
                "UPDATE users SET email_token = NULL, email_token_expires_at = NULL "
                "WHERE email_token IS NOT NULL"
            )
        )
        tokens_email = result.rowcount
        print(f"  [OK] Email tokens invalidados: {tokens_email}")

        session.commit()

    db = get_mongo_sync_db()
    db[AUDIT_LOG_COLLECTION].insert_one({
        "user_id": "SYSTEM",
        "timestamp": datetime.now(UTC).replace(tzinfo=None),
        "operation": "security.incident.containment_executed",
        "entity_name": "System",
        "from_value": {},
        "to_value": {
            "tokens_revogados": tokens_revogados,
            "codes_removidos": codes_removidos,
            "email_tokens_invalidados": tokens_email,
        },
    })
    print("  [OK] Evento registrado no audit log (MongoDB)\n")

    print("=" * 60)
    print("CONTENÇÃO CONCLUÍDA. PRÓXIMOS PASSOS:")
    print("  1. Parar a API:   docker-compose stop api")
    print("  2. Avaliar impacto: consulte docs/security/data-breach-response.md")
    print("  3. Notificar ANPD em até 72h se dados pessoais foram expostos")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n[ERRO] Falha na contenção: {exc}", file=sys.stderr)
        sys.exit(1)

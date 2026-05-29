"""
Security incident containment script — Thunderstone

Execution (inside the container):
    docker-compose exec api python backend/scripts/contain.py

What it does:
    1. Revokes all active OAuth2 tokens (sets access_token_revoked_at and refresh_token_revoked_at to current epoch)
    2. Removes all pending authorization codes
    3. Clears email_token from all users
    4. Records the containment action in the MongoDB audit log
    5. Prints next steps
"""

import sys
from datetime import datetime, UTC

from sqlalchemy import text

from backend.database import SyncSession, get_mongo_sync_db
from backend.core.audit_log import AUDIT_LOG_COLLECTION


def main() -> None:
    print(f"\n[{datetime.now(UTC).isoformat()}] Starting incident containment...\n")

    with SyncSession() as session:
        result = session.execute(
            text(
                "UPDATE oauth2_tokens "
                "SET access_token_revoked_at = EXTRACT(EPOCH FROM NOW())::int, "
                "    refresh_token_revoked_at = EXTRACT(EPOCH FROM NOW())::int "
                "WHERE access_token_revoked_at = 0"
            )
        )
        tokens_revoked = result.rowcount
        print(f"  [OK] OAuth2 tokens revoked: {tokens_revoked}")

        result = session.execute(text("DELETE FROM oauth2_authorization_codes"))
        codes_removed = result.rowcount
        print(f"  [OK] Authorization codes removed: {codes_removed}")

        result = session.execute(
            text(
                "UPDATE users SET email_token = NULL, email_token_expires_at = NULL "
                "WHERE email_token IS NOT NULL"
            )
        )
        email_tokens_cleared = result.rowcount
        print(f"  [OK] Email tokens cleared: {email_tokens_cleared}")

        session.commit()

    db = get_mongo_sync_db()
    db[AUDIT_LOG_COLLECTION].insert_one({
        "user_id": "SYSTEM",
        "timestamp": datetime.now(UTC).replace(tzinfo=None),
        "operation": "security.incident.containment_executed",
        "entity_name": "System",
        "from_value": {},
        "to_value": {
            "tokens_revoked": tokens_revoked,
            "codes_removed": codes_removed,
            "email_tokens_cleared": email_tokens_cleared,
        },
    })
    print("  [OK] Event recorded in MongoDB audit log\n")

    print("=" * 60)
    print("CONTAINMENT COMPLETE. NEXT STEPS:")
    print("  1. Stop the API:  docker-compose stop api")
    print("  2. Assess impact: see docs/security/data-breach-response.md")
    print("  3. Notify ANPD within 72h if personal data was exposed")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n[ERROR] Containment failed: {exc}", file=sys.stderr)
        sys.exit(1)

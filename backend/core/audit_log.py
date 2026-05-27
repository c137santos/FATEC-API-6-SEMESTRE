from enum import Enum
from typing import Any


class Operation(str, Enum):
    # Autenticação
    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILURE = "auth.login.failure"
    AUTH_LOGIN_BLOCKED = "auth.login.blocked"
    AUTH_LOGOUT = "auth.logout"
    AUTH_PASSWORD_RESET = "auth.password.reset_requested"
    # Cadastro e Conta
    ACCOUNT_CREATED = "account.created"
    ACCOUNT_UPDATED = "account.updated"
    ACCOUNT_DELETION = "account.deletion"
    # Consentimento
    CONSENT_ACCEPTED = "consent.accepted"
    CONSENT_REVOKED = "consent.revoked"
    # Segurança
    SECURITY_UNAUTHORIZED = "security.unauthorized_access"
    SECURITY_TOKEN_INVALID = "security.token.invalid"
    SECURITY_RATE_LIMIT = "security.rate_limit.hit"
    # Relatório
    REPORT_REQUESTED = "report.requested"
    REPORT_GENERATED = "report.generated"
    REPORT_FAILED = "report.failed"
    # Logs
    AUDIT_LOGS_EXPORTED = "report.audit_logs.exported"


AUDIT_LOG_COLLECTION = "audit_logs"

# Campos que nunca devem aparecer nos logs (RN02 — Zero-PII)
_PII_KEYS: frozenset[str] = frozenset({
    "email", "name", "full_name", "first_name", "last_name",
    "phone", "phone_number", "cpf", "cnpj", "address",
    "password", "password_hash", "new_password", "email_token",
    "secret", "token",
})


def _sanitize(data: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {}
    return {k: v for k, v in data.items() if k.lower() not in _PII_KEYS}

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.audit_log import Operation, _PII_KEYS, _sanitize
from backend.services.audit_log_service import write_log


# --- _sanitize ---

def test_sanitize_removes_pii_keys():
    data = {"username": "joao", "email": "joao@example.com", "cpf": "123", "role": "admin"}
    result = _sanitize(data)
    assert result == {"username": "joao", "role": "admin"}


def test_sanitize_is_case_insensitive():
    data = {"Email": "x@x.com", "PASSWORD": "secret123", "name": "Maria", "id": 1}
    result = _sanitize(data)
    assert result == {"id": 1}


def test_sanitize_returns_empty_dict_for_none():
    assert _sanitize(None) == {}


def test_sanitize_returns_empty_dict_for_empty_dict():
    assert _sanitize({}) == {}


def test_sanitize_keeps_non_pii_fields():
    data = {"status": "active", "role": "user", "plan": "free"}
    assert _sanitize(data) == data


def test_sanitize_removes_all_known_pii_keys():
    data = {key: "value" for key in _PII_KEYS}
    assert _sanitize(data) == {}


def test_sanitize_does_not_mutate_original():
    data = {"email": "a@b.com", "role": "admin"}
    _sanitize(data)
    assert "email" in data


# --- write_log ---

@pytest.mark.asyncio
async def test_write_log_inserts_document():
    mock_collection = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)

    with patch("backend.services.audit_log_service.get_mongo_async_db", return_value=mock_db):
        await write_log(
            operation=Operation.AUTH_LOGIN_SUCCESS,
            user_id=42,
            entity_name="User",
            from_value={"status": "inactive"},
            to_value={"status": "active"},
        )

    mock_collection.insert_one.assert_awaited_once()
    doc = mock_collection.insert_one.call_args[0][0]
    assert doc["user_id"] == "42"
    assert doc["operation"] == Operation.AUTH_LOGIN_SUCCESS.value
    assert doc["entity_name"] == "User"
    assert doc["from_value"] == {"status": "inactive"}
    assert doc["to_value"] == {"status": "active"}
    assert "timestamp" in doc


@pytest.mark.asyncio
async def test_write_log_sanitizes_pii_in_values():
    mock_collection = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)

    with patch("backend.services.audit_log_service.get_mongo_async_db", return_value=mock_db):
        await write_log(
            operation=Operation.ACCOUNT_UPDATED,
            user_id=1,
            from_value={"email": "old@x.com", "role": "user"},
            to_value={"email": "new@x.com", "role": "admin"},
        )

    doc = mock_collection.insert_one.call_args[0][0]
    assert "email" not in doc["from_value"]
    assert "email" not in doc["to_value"]
    assert doc["from_value"] == {"role": "user"}
    assert doc["to_value"] == {"role": "admin"}


@pytest.mark.asyncio
async def test_write_log_swallows_db_exception(caplog):
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(side_effect=Exception("mongo down"))

    with patch("backend.services.audit_log_service.get_mongo_async_db", return_value=mock_db):
        await write_log(
            operation=Operation.SECURITY_UNAUTHORIZED,
            user_id=99,
        )
    # deve logar o erro sem propagar a exceção


@pytest.mark.asyncio
async def test_write_log_with_none_values():
    mock_collection = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)

    with patch("backend.services.audit_log_service.get_mongo_async_db", return_value=mock_db):
        await write_log(
            operation=Operation.AUTH_LOGOUT,
            user_id="abc",
        )

    doc = mock_collection.insert_one.call_args[0][0]
    assert doc["from_value"] == {}
    assert doc["to_value"] == {}

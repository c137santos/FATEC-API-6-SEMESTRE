from unittest.mock import patch, AsyncMock
import pytest
from backend.email.envio_email import send_email
from fastapi import HTTPException

class MockUser:
    def __init__(self, email):
        self.email = email

@pytest.mark.asyncio
async def test_send_email_success():
    user = MockUser(email="cliente@exemplo.com")
    
    with patch("backend.email.envio_email.FastMail") as MockFastMail:
        instance = MockFastMail.return_value
        instance.send_message = AsyncMock()

        await send_email(user) 

        instance.send_message.assert_awaited_once()
        
        args, _ = instance.send_message.call_args
        message = args[0]
        
        assert message.subject == "Relatório automático"

        recipients_list = [r.email if hasattr(r, 'email') else r for r in message.recipients]
        assert "cliente@exemplo.com" in recipients_list

@pytest.mark.asyncio
async def test_send_email_error_log(capsys):
    """Testa a captura de erro caso o servidor SMTP falhe."""
    user = MockUser(email="erro@exemplo.com")

    with patch("backend.email.envio_email.FastMail") as MockFastMail:
        instance = MockFastMail.return_value
        instance.send_message = AsyncMock(side_effect=Exception("Falha na conexão"))

        with pytest.raises(HTTPException) as exc_info:
            await send_email(user)

        assert exc_info.value.status_code == 500
        assert "Falha na conexão" in exc_info.value.detail
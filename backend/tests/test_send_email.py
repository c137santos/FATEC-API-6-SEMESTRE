import pytest
import os
from unittest.mock import patch, AsyncMock
from backend.email.envio_email import send_email
from backend.email.envio_email import generate_pdf_report
from fastapi import HTTPException


class MockUser:
    def __init__(self, email):
        self.email = email

user = MockUser(email="cliente@exemplo.com")

@pytest.mark.asyncio
async def test_send_email_success():
    """Testa o envio básico com anexo mockado."""
    file_path = "relatorio_teste.pdf"

    with patch("backend.email.envio_email.FastMail") as MockFastMail, \
         patch("backend.email.envio_email.MessageSchema") as MockMessageSchema, \
         patch("backend.email.envio_email.Path.is_file", return_value=True):
        
        instance = MockFastMail.return_value
        instance.send_message = AsyncMock()
        
        await send_email(user, file_path) 

        assert instance.send_message.called
        MockMessageSchema.assert_called_once()
        
        _, kwargs = MockMessageSchema.call_args
        attachment = kwargs["attachments"][0]
        assert str(attachment).endswith("relatorio_teste.pdf")

@pytest.mark.asyncio
async def test_send_email_file_not_found():
    """Testa se a função lança 404 quando o arquivo não existe."""
    file_path = "arquivo_inexistente.pdf"

    with patch("backend.email.envio_email.Path.is_file", return_value=False):
        with pytest.raises(HTTPException) as excinfo:
            await send_email(user, file_path)
        
        assert excinfo.value.status_code == 404
        assert "não foi encontrado" in excinfo.value.detail

@pytest.mark.asyncio
async def test_send_email_smtp_error():
    """Testa erro de envio quando o arquivo EXISTE mas o SMTP falha."""
    file_path = "relatorio_valido.pdf"

    with patch("backend.email.envio_email.Path.is_file", return_value=True), \
         patch("backend.email.envio_email.FastMail") as MockFastMail:
        
        instance = MockFastMail.return_value
        instance.send_message = AsyncMock(side_effect=Exception("Conexão recusada"))

        with pytest.raises(HTTPException) as excinfo:
            await send_email(user, file_path)
        
        assert excinfo.value.status_code == 500
        assert "Falha na comunicação" in excinfo.value.detail

@pytest.mark.asyncio
async def test_generate_pdf_integration():
    """Testa se a geração de PDF e o envio podem trabalhar juntos (Mockando apenas o SMTP)."""
    
    with patch("backend.email.envio_email.FastMail") as MockFastMail:
        instance = MockFastMail.return_value
        instance.send_message = AsyncMock()

        path = await generate_pdf_report(user.email)
        
        try:
            await send_email(user, path)
            assert instance.send_message.called
        finally:
            if os.path.exists(path):
                os.remove(path)
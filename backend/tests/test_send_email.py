from unittest.mock import patch, AsyncMock
import pytest
from backend.email.envio_email import send_email
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
         patch("os.path.exists", return_value=True):
        
        instance = MockFastMail.return_value
        instance.send_message = AsyncMock()
        
        mock_msg = MockMessageSchema.return_value

        await send_email(user, file_path) 

        assert instance.send_message.called
        
        MockMessageSchema.assert_called_once()
        _, kwargs = MockMessageSchema.call_args
        assert kwargs["attachments"] == [file_path]
        assert kwargs["recipients"] == [user.email]

@pytest.mark.asyncio
async def test_send_email_file_not_found(capsys):
    """Testa se a função interrompe o envio caso o arquivo não exista."""
    file_path = "arquivo_fantasma.pdf"

    with patch("os.path.exists", return_value=False):
        await send_email(user, file_path)

        captured = capsys.readouterr()
        assert f"Erro: O arquivo {file_path} não existe." in captured.out

@pytest.mark.asyncio
async def test_send_email_smtp_error(capsys):
    """Testa a captura de erro genérico caso o FastMail falhe."""
    file_path = "relatorio.pdf"

    with patch("backend.email.envio_email.FastMail") as MockFastMail, \
         patch("os.path.exists", return_value=True):
        
        instance = MockFastMail.return_value
        instance.send_message = AsyncMock(side_effect=Exception("Erro SMTP Genérico"))

        await send_email(user, file_path)

        captured = capsys.readouterr()
        assert "Ocorreu um erro ao enviar o e-mail" in captured.out

@pytest.mark.asyncio
async def test_generate_pdf_integration():
    """Testa se a geração de PDF e o envio podem trabalhar juntos (Mockando apenas o SMTP)."""
    
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

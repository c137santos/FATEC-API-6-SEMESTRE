import os
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi import HTTPException, status

from backend.email.envio_email import send_email


class MockUser:
    def __init__(self, email):
        self.email = email

user_mock = MockUser(email="cliente@exemplo.com")

@pytest.mark.asyncio
async def test_send_email_success():
    """Testa o envio com sucesso e se os componentes são chamados."""
    file_path = "relatorio_teste.pdf"
    
    with patch("backend.email.envio_email.FastMail") as MockFastMail, \
         patch("backend.email.envio_email.MessageSchema"), \
         patch("backend.email.envio_email.Path.is_file", return_value=True), \
         patch("os.remove"): 
        
        instance = MockFastMail.return_value
        instance.send_message = AsyncMock()
        
        await send_email(user_mock, file_path) 
        instance.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_post_send_email_accepted(client):
    """Testa se a rota retorna 202 e aciona a tarefa de background."""
    payload = {"email": "yan@fatec.sp.gov.br"}

    with patch("backend.routes.email.report_workflow") as mock_workflow:
        response = await client.post("/relatorios/enviar", json=payload)
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.json()["status"] == "success"
        mock_workflow.assert_called_once()


@pytest.mark.asyncio
async def test_post_send_email_invalid_format(client):
    """Testa a validação automática do e-mail (Pydantic)."""
    payload = {"email": "email-sem-formato-correto"}
    response = await client.post("/relatorios/enviar", json=payload)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_send_email_file_not_found():
    """Garante erro 404 se o arquivo do relatório sumir antes do envio."""
    file_path = "arquivo_que_nao_existe.pdf"
    
    with patch("backend.email.envio_email.Path.is_file", return_value=False):
        with pytest.raises(HTTPException) as excinfo:
            await send_email(user_mock, file_path)
        assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_send_email_smtp_error():
    """Garante erro 500 se o servidor de e-mail falhar."""
    file_path = "relatorio_valido.pdf"
    
    with patch("backend.email.envio_email.Path.is_file", return_value=True), \
         patch("backend.email.envio_email.FastMail") as MockFastMail, \
         patch("os.remove"):
        
        instance = MockFastMail.return_value
        instance.send_message = AsyncMock(side_effect=Exception("Timeout SMTP"))

        with pytest.raises(HTTPException) as excinfo:
            await send_email(user_mock, file_path)
        assert excinfo.value.status_code == 500


@pytest.mark.asyncio
async def test_generate_pdf_integration():
    """
    Testa o fluxo de envio garantindo que nenhuma dependência externa 
    (Config, Schema ou SMTP) dispare exceções.
    """
    file_path = "relatorio_final_test.pdf"
    
    with patch("backend.email.envio_email.get_mail_config"), \
         patch("backend.email.envio_email.MessageSchema"), \
         patch("backend.email.envio_email.FastMail") as mock_fastmail, \
         patch("backend.email.envio_email.Path.is_file", return_value=True), \
         patch("backend.email.envio_email.Path.exists", return_value=True), \
         patch("backend.email.envio_email.os.remove") as mock_remove:
        
        instance = mock_fastmail.return_value
        instance.send_message = AsyncMock()

        await send_email(user_mock, file_path=file_path)
        
        instance.send_message.assert_awaited_once()
        
        mock_remove.assert_called_once_with(file_path)


@pytest.mark.asyncio
async def test_send_email_error_log(): 
    
    with patch('backend.email.envio_email.FastMail') as MockFastMail, \
         patch('backend.email.envio_email.Path.is_file', return_value=True), \
         patch('os.remove'):
        
        instance = MockFastMail.return_value
        instance.send_message = AsyncMock(
            side_effect=Exception('Falha na conexão')
        )

        with pytest.raises(HTTPException) as exc_info:
            await send_email(user_mock, file_path="relatorio_teste.pdf")

        assert exc_info.value.status_code == 500
        assert "Falha na comunicação" in exc_info.value.detail


@pytest.mark.asyncio
async def test_send_email_cleanup_on_success():
    """
    Teste de 'Caminho Feliz' com IO: 
    Verifica se o arquivo real é removido após o fluxo.
    """
    file_path = "temp_unit_test.pdf"
    with open(file_path, "w") as f:
        f.write("pdf content")

    with patch("backend.email.envio_email.FastMail") as MockFastMail, \
         patch("backend.email.envio_email.get_mail_config"):
        
        MockFastMail.return_value.send_message = AsyncMock()
        
        await send_email(user_mock, file_path)
        
        assert not os.path.exists(file_path)


@pytest.mark.asyncio
async def test_report_workflow_integration(capsys):
    """Testa se o workflow orquestra as duas funções corretamente."""
    from backend.routes.email import report_workflow
    
    with patch("backend.routes.email.generate_pdf_report", new_callable=AsyncMock) as mock_gen, \
         patch("backend.routes.email.send_email", new_callable=AsyncMock) as mock_send:
        
        mock_gen.return_value = "/tmp/fake.pdf"
        
        await report_workflow(user_mock)
        
        mock_gen.assert_awaited_once_with(user_mock.email)
        mock_send.assert_awaited_once_with(user_mock, "/tmp/fake.pdf")
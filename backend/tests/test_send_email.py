from unittest.mock import patch, AsyncMock, MagicMock
import pytest
from backend.email.envio_email import send_email


@pytest.mark.asyncio
async def test_send_email_success():
    mock_message = MagicMock()
    mock_message.subject = 'Seu relatório está pronto — Thunderstone'
    mock_message.recipients = ['cliente@exemplo.com']

    with patch('backend.email.envio_email.MessageSchema', return_value=mock_message), \
         patch('backend.email.envio_email.FastMail') as MockFastMail:
        instance = MockFastMail.return_value
        instance.send_message = AsyncMock()

        await send_email('cliente@exemplo.com', '/tmp/report.pdf')

        instance.send_message.assert_awaited_once()

        args, _ = instance.send_message.call_args
        message = args[0]

        assert message.subject == 'Seu relatório está pronto — Thunderstone'
        assert 'cliente@exemplo.com' in message.recipients


@pytest.mark.asyncio
async def test_send_email_propagates_exception():
    """Erro do servidor SMTP deve propagar normalmente."""
    mock_message = MagicMock()

    with patch('backend.email.envio_email.MessageSchema', return_value=mock_message), \
         patch('backend.email.envio_email.FastMail') as MockFastMail:
        instance = MockFastMail.return_value
        instance.send_message = AsyncMock(side_effect=Exception('Falha na conexão'))

        with pytest.raises(Exception, match='Falha na conexão'):
            await send_email('erro@exemplo.com', '/tmp/report.pdf')

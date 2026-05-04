import asyncio
import logging
from pathlib import Path

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from backend.settings import Settings

logger = logging.getLogger(__name__)
settings = Settings()


def get_mail_config():
    return ConnectionConfig(
        MAIL_USERNAME=settings.mail_username,
        MAIL_PASSWORD=settings.mail_password,
        MAIL_FROM=settings.mail_from,
        MAIL_PORT=settings.mail_port,
        MAIL_SERVER=settings.mail_server,
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
    )


async def send_email(recipient_email: str, pdf_path: str) -> None:
    conf = get_mail_config()

    pdf_file = Path(pdf_path)
    attachments = [
        {
            'file': pdf_path,
            'filename': pdf_file.name,
            'mime_type': 'application',
            'mime_subtype': 'pdf',
        }
    ]

    message = MessageSchema(
        subject='Seu relatório está pronto — Thunderstone',
        recipients=[recipient_email],
        body=(
            'Olá,\n\n'
            'Seu relatório foi gerado com sucesso no sistema Thunderstone.\n'
            'O arquivo PDF está em anexo.\n\n'
            'Atenciosamente,\nEquipe Thunderstone'
        ),
        subtype=MessageType.plain,
        attachments=attachments,
    )

    fm = FastMail(conf)
    await fm.send_message(message)
    logger.info('[send_email] E-mail enviado para %s', recipient_email)


def send_email_sync(recipient_email: str, pdf_path: str) -> None:
    asyncio.run(send_email(recipient_email, pdf_path))

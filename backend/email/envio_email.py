import asyncio
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi import HTTPException
from backend.core.models import User
from backend.settings import Settings


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


async def send_email(user: User):
    """
    Envia o e-mail para o endereço do usuário (user.email).
    :param user: Objeto que contém o atributo 'email'
    """
    try:
        conf = get_mail_config()

        message = MessageSchema(
            subject='Relatório automático',
            recipients=[user.email],
            body='Olá, seu relatório foi gerado com sucesso no sistema.',
            subtype=MessageType.plain,
        )

        fm = FastMail(conf)
        await fm.send_message(message)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f'Ocorreu um erro ao enviar o e-mail: {str(e)}',
        )


if __name__ == '__main__':

    class MockUser:
        def __init__(self, email):
            self.email = email

    test_user = MockUser(email='yan_teste@exemplo.com')

    try:
        asyncio.run(send_email(user=test_user))
    finally:
        pass

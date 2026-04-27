import asyncio
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi import HTTPException
from core.models import User
from settings import Settings

settings = Settings()

def get_mail_config():
    return ConnectionConfig(
        MAIL_USERNAME = settings.mail_username,
        MAIL_PASSWORD = settings.mail_password,
        MAIL_FROM = settings.mail_from,
        MAIL_PORT = settings.mail_port,
        MAIL_SERVER = settings.mail_server,
        MAIL_STARTTLS = True,
        MAIL_SSL_TLS = False,
        USE_CREDENTIALS = True,
        VALIDATE_CERTS = True
    )

async def generate_pdf_report(user_email: str) -> str:
    def create_pdf():
        file_path = f"relatorio_{user_email.split('@')[0]}.pdf"
        
        c = canvas.Canvas(file_path, pagesize=A4)
        width, height = A4
        
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, height - 50, "Relatório Automático")
        
        c.setFont("Helvetica", 12)
        c.drawString(100, height - 80, f"Destinatário: {user_email}")
        c.drawString(100, height - 100, "Este é um documento PDF real gerado pela aplicação.")
        
        c.showPage()
        c.save()
        
        return file_path
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, create_pdf)

async def send_email(user: User, file_path: str):
    """
    Envia o e-mail para o endereço do usuário (user.email).
    :param user: Objeto que contém o atributo 'email'
    """
    try:

        conf = get_mail_config()

        message = MessageSchema(
            subject="Relatório automático",
            recipients=[user.email], 
            body="Olá, segue em anexo o relatório gerado.",
            subtype=MessageType.plain,
            attachments=[file_path]
        )

        fm = FastMail(conf)
        await fm.send_message(message)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro ao enviar o e-mail: {str(e)}")

if __name__ == "__main__":

    class MockUser:
        def __init__(self, email):
            self.email = email

    test_user = MockUser(email="yan_teste@exemplo.com")
    
    try:
        asyncio.run(send_email(user=test_user))
    finally:
        pass

import asyncio
from pathlib import Path
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi import HTTPException, status
from core.models import User
from settings import Settings

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

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
    :param file_path: Caminho do arquivo (PDF) já existente para anexo
    """
    path = Path(file_path)
    
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"O anexo {file_path} não foi encontrado ou não é um arquivo válido."
        )
    
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Falha na comunicação com o servidor de e-mail: {str(e)}"
        )
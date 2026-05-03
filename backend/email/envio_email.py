import os
import uuid
import tempfile
import asyncio
from pathlib import Path
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi import HTTPException, status
from backend.core.models import User
from backend.settings import Settings

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

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


def _create_pdf_worker(user_email: str) -> str:
    unique_id = uuid.uuid4().hex
    filename = f"relatorio_{unique_id}.pdf"
    
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, filename)
    
    try:
        c = canvas.Canvas(file_path, pagesize=A4)
        _, height = A4
        
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, height - 50, "Relatório Automático")
        
        c.setFont("Helvetica", 12)
        c.drawString(100, height - 80, f"Destinatário: {user_email}")
        c.drawString(100, height - 100, "Este é um documento PDF real gerado pela aplicação.")
        
        c.showPage()
        c.save()
        
        return file_path
    except Exception as e:
        print(f"Erro ao gerar PDF: {e}")
        raise

async def generate_pdf_report(user_email: str) -> str:
    return await asyncio.to_thread(_create_pdf_worker, user_email)

async def send_email(user: User, file_path: str):
    """
    Envia o e-mail e garante a exclusão do arquivo anexo após o processo.
    """
    path = Path(file_path)
    
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"O anexo {file_path} não foi encontrado."
        )
    
    try:
        conf = get_mail_config()

        message = MessageSchema(
            subject='Relatório automático',
            recipients=[user.email],
            body='Olá, seu relatório foi gerado com sucesso no sistema.',
            subtype=MessageType.plain,
            attachments=[file_path]
        )

        fm = FastMail(conf)
        await fm.send_message(message)

    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Falha na comunicação com o servidor de e-mail."
        )
    finally:
        try:
            if path.exists():
                os.remove(file_path)
        except Exception as cleanup_error:
            print(f"Erro ao remover arquivo temporário {file_path}: {cleanup_error}")
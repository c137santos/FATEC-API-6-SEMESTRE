import logging
from fastapi import APIRouter, BackgroundTasks, status
from pydantic import EmailStr, BaseModel

from backend.email.envio_email import send_email, generate_pdf_report

logger = logging.getLogger(__name__)

router = APIRouter()

class UserEmailSchema(BaseModel):
    email: EmailStr


async def report_workflow(user: UserEmailSchema):
    """
    Função orquestradora que será executada totalmente em background.
    """
    try:
        
        file_path = await generate_pdf_report(user.email)
        await send_email(user, file_path)
    except Exception as e:
        logger.error(f"Erro no workflow de e-mail para {user.email}: {e}")


@router.post('/relatorios/enviar', status_code=status.HTTP_202_ACCEPTED)
async def post_send_email(user_data: UserEmailSchema, background_tasks: BackgroundTasks):

    try:
        background_tasks.add_task(report_workflow, user_data)
    
        return {
            "status": "success",
            "message": f"E-mail para {user_data.email} está sendo processado para envio"
        }

    except Exception as e:
        logger.error(f"Erro no servidor: {e}")
from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from pydantic import EmailStr, BaseModel

from backend.email.envio_email import send_email, generate_pdf_report

router = APIRouter()

class UserEmailSchema(BaseModel):
    email: EmailStr


@router.post('/relatorios/enviar', status_code=status.HTTP_202_ACCEPTED)
async def post_send_email(user_data: UserEmailSchema, background_tasks: BackgroundTasks):
    try:

        file_path = await generate_pdf_report(user_data.email)
        background_tasks.add_task(send_email, user_data, file_path)

        return {
            "status": "success",
            "message": f"E-mail para {user_data.email} está sendo processado para envio"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail="Erro no servidor: " + str(e))
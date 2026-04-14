import pandas as pd
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

load_dotenv()

conf = ConnectionConfig(
    MAIL_USERNAME = os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD"),
    MAIL_FROM = os.getenv("MAIL_FROM"),
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587)), 
    MAIL_SERVER = os.getenv("MAIL_SERVER"),
    MAIL_STARTTLS = True,
    MAIL_SSL_TLS = False,
    USE_CREDENTIALS = True
)

async def gerar_e_enviar_relatorio():
    nome_do_arquivo_csv = "ucat_pj.csv" 
    downloads_path = str(Path.home() / "Downloads")
    fn = os.path.join(downloads_path, nome_do_arquivo_csv)
    pdf_filename = "relatorio_ucat_pj.pdf"

    try:
        try:
            df = pd.read_csv(fn, encoding='utf-8', sep=';')
        except UnicodeDecodeError:
            df = pd.read_csv(fn, encoding='latin1', sep=';')
        
        doc = SimpleDocTemplate(pdf_filename, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("Relatório de Dados do Arquivo CSV", styles['Title']))
        story.append(Paragraph(f"Origem: {fn}", styles['Normal']))
        story.append(Paragraph("<br/><br/>", styles['Normal'])) 

        num_rows_to_display = 20
        num_cols_to_display = 10 
        
        data_for_pdf = [df.columns[:num_cols_to_display].tolist()] + \
                       df.head(num_rows_to_display).iloc[:, :num_cols_to_display].values.tolist()

        table = Table(data_for_pdf)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        
        story.append(table)
        doc.build(story)
        print(f"PDF '{pdf_filename}' criado com sucesso.")

        message = MessageSchema(
            subject="Relatório UCAT PJ - Automático",
            recipients=["yanyamim@gmail.com"], 
            body="Olá, segue em anexo o relatório gerado a partir do CSV.",
            subtype=MessageType.plain,
            attachments=[pdf_filename]
        )

        fm = FastMail(conf)
        await fm.send_message(message)
        print("E-mail enviado com sucesso!")

    except FileNotFoundError:
        print(f"Erro: O arquivo '{nome_do_arquivo_csv}' não foi encontrado em Downloads.")
    except Exception as e:
        print(f"Ocorreu um erro: {e}")

if __name__ == "__main__":
    asyncio.run(gerar_e_enviar_relatorio())
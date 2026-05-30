import io
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from PIL import Image as PilImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

PASTA_RAIZ = Path(__file__).resolve().parent.parent
_OUTPUT_BASE = Path(
    os.getenv('REPORTS_DIR', str(Path(__file__).resolve().parent.parent.parent / 'output' / 'reports'))
)

_CHARTS = [
    (
        'grafico_tam', 
        lambda sig, ano: f'Top 10 Maiores Trechos (TAM) — {sig} ({ano})'
    ),
    (
        'pt_pnt', 
        lambda sig, ano: f'Perdas Técnicas e Não Técnicas (PT x PNT) — {sig} ({ano})'
    ),
    (
        'tabela_score', 
        lambda sig, ano: f'Score de Criticidade — {sig} ({ano})'
    ),
    (
        'mapa_calor', 
        lambda sig, ano: f'Mapa de Calor de Criticidade — {sig} ({ano})'
    ),
    (
        'grafico_sam', 
        lambda sig, ano: f'Gráfico de todos os Conjuntos (SAM)\n{sig} | Ano: {ano}'
    ),
    (
        'prophet_DEC', 
        lambda sig, ano: f'Previsão de Série Temporal com Prophet (DEC) — {sig} ({ano})'
    ),
    (
        'prophet_FEC', 
        lambda sig, ano: f'Previsão de Série Temporal com Prophet (FEC) — {sig} ({ano})'
    ),
]

_PAGE_W = A4[0]
_PAGE_H = A4[1]
_MARGIN_TOP = 2 * cm
_MARGIN_BOT = 2 * cm
_MARGIN_LR = 1.5 * cm
_FRAME_PAD = 6  # SimpleDocTemplate adds 6pt internal padding per side
_USABLE_W = _PAGE_W - 2 * _MARGIN_LR - 2 * _FRAME_PAD
_USABLE_H = _PAGE_H - _MARGIN_TOP - _MARGIN_BOT - 2 * _FRAME_PAD


def _reports_dir(job_id: str) -> Path:
    path = _OUTPUT_BASE / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _placeholder_png(path: Path, title: str) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(12, 3))
    ax.set_axis_off()
    ax.text(
        0.5, 0.5,
        f'{title}\nDados insuficientes para gerar este gráfico.',
        ha='center', va='center', fontsize=12, color='#888888',
        transform=ax.transAxes,
    )
    plt.savefig(str(path), dpi=100, bbox_inches='tight')
    plt.close(fig)


def _safe_filename(name: str) -> str:
    return ''.join(c if c.isalnum() or c in ' _-' else '_' for c in name).strip()


def _image_flowables(img_path: Path, max_width: float, first_chunk_height: float) -> list:

    pil_img = PilImage.open(str(img_path)).convert('RGB')


    w, h = pil_img.size
    last_content_row = h - 1
    for y in range(h - 1, -1, -1):
        if min(pil_img.crop((0, y, w, y + 1)).tobytes()) < 245:
            last_content_row = y
            break
    if last_content_row < h - 1:
        pil_img = pil_img.crop((0, 0, w, last_content_row + 5))

    iw, ih = pil_img.size

    scale = max_width / iw
    scaled_h = ih * scale

    if scaled_h <= first_chunk_height:
        buf = io.BytesIO()
        pil_img.save(buf, format='PNG')
        buf.seek(0)
        return [Image(buf, width=iw * scale, height=scaled_h)]
    flowables = []
    chunk_heights = [first_chunk_height, _USABLE_H]
    y_px = 0
    chunk_idx = 0

    while y_px < ih:
        avail_pt = chunk_heights[min(chunk_idx, len(chunk_heights) - 1)]
        slice_px = int(avail_pt / scale)
        slice_px = min(slice_px, ih - y_px)

        strip = pil_img.crop((0, y_px, iw, y_px + slice_px))
        buf = io.BytesIO()
        strip.save(buf, format='PNG')
        buf.seek(0)

        strip_w_pt = iw * scale
        strip_h_pt = slice_px * scale
        flowables.append(Image(buf, width=strip_w_pt, height=strip_h_pt))

        y_px += slice_px
        chunk_idx += 1
        if y_px < ih:
            flowables.append(PageBreak())

    return flowables


def gerar_pdf_report(job_id: str, render_paths: dict, job_meta: dict) -> str:
    out_dir = _reports_dir(job_id)

    dist_name = _safe_filename(job_meta.get('dist_name', 'distribuidora'))
    ano = job_meta.get('ano_gdb', '')
    pdf_filename = f'report_{dist_name}_{ano}.pdf' if ano else f'report_{dist_name}.pdf'
    pdf_path = out_dir / pdf_filename
    placeholder_dir = out_dir / 'placeholders'
    placeholder_dir.mkdir(exist_ok=True)
    prophet_paths = render_paths.get('prophet') or {}
    render_paths = {
        **render_paths,
        'prophet_DEC': prophet_paths.get('DEC'),
        'prophet_FEC': prophet_paths.get('FEC'),
    }

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ReportTitle', parent=styles['Title'], fontSize=18, spaceAfter=10,
        alignment=0  
    )
    meta_style = ParagraphStyle(
        'ReportMeta', parent=styles['Normal'], fontSize=9,
        textColor=colors.grey, spaceAfter=4,
    )
    section_style = ParagraphStyle(
        'ReportSection', parent=styles['Heading2'],
        fontSize=13, spaceBefore=16, spaceAfter=8,
    )
    
    logo_text_style = ParagraphStyle(
        'LogoText', parent=styles['Normal'], fontSize=8,
        fontName='Helvetica-Bold', textColor=colors.HexColor('#222222'),
        alignment=1  
    )

    dist_name = job_meta.get('dist_name', 'Distribuidora')

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        topMargin=_MARGIN_TOP, bottomMargin=_MARGIN_BOT,
        leftMargin=_MARGIN_LR, rightMargin=_MARGIN_LR,
    )

    data_emissao = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y %H:%M")
    col_esquerda = [
        Paragraph(f'Relatório de Análise — {dist_name}', title_style),
        Paragraph(f'Ano: {ano} | Job ID: {job_id}', meta_style),
        Paragraph(f'Gerado em: {data_emissao}', meta_style),
    ]
    logo_path = PASTA_RAIZ / 'docs' / 'img' / 'thunderstone.png'
    col_direita = []
    
    if logo_path.exists():
        with PilImage.open(str(logo_path)) as pil_img:
            orig_w, orig_h = pil_img.size
            
        largura_desejada = 65.0
        
        altura_proporcional = (largura_desejada * orig_h) / orig_w
        
        logo_img = Image(str(logo_path), width=largura_desejada, height=altura_proporcional)
        logo_img.hAlign = 'CENTER'
        col_direita.append(logo_img)
        col_direita.append(Spacer(1, 3))  
    else:
        logger.warning('[gerar_pdf_report] Logo da Thunderstone não encontrado em %s', logo_path)
    
    col_direita.append(Paragraph('Thunderstone', logo_text_style))
    largura_esq = _USABLE_W * 0.80
    largura_dir = _USABLE_W * 0.20
    
    header_table = Table([[col_esquerda, col_direita]], colWidths=[largura_esq, largura_dir])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),   
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),      
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),  
    ]))

    story = [
        header_table,
        HRFlowable(width='100%', thickness=1, color=colors.lightgrey, spaceAfter=20),
    ]

    title_overhead = 50
    first_chunk_h = _USABLE_H - title_overhead

    sig_agente = job_meta.get('dist_name', 'Distribuidora')
    ano_atual = job_meta.get('ano_gdb', 'S/A')

    for i, (key, titulo_or_func) in enumerate(_CHARTS):
        if i > 0:
            story.append(PageBreak())  

        if callable(titulo_or_func):
            section_title = titulo_or_func(sig_agente, ano_atual)
        else:
            section_title = str(titulo_or_func)

        story.append(Paragraph(section_title, section_style))
        story.append(Spacer(1, 8))

        img_path_str = render_paths.get(key)
        img_path = Path(img_path_str) if img_path_str else None

        if not img_path or not img_path.exists():
            logger.info('[gerar_pdf_report] Placeholder para %s. job_id=%s', key, job_id)
            img_path = placeholder_dir / f'placeholder_{key}.png'
            _placeholder_png(img_path, section_title)

        try:
            story.extend(_image_flowables(img_path, _USABLE_W, first_chunk_h))
        except Exception:
            logger.warning(
                '[gerar_pdf_report] Falha ao incluir imagem %s, gerando placeholder. job_id=%s',
                key, job_id,
            )
            img_path = placeholder_dir / f'placeholder_{key}_err.png'
            _placeholder_png(img_path, section_title)
            story.extend(_image_flowables(img_path, _USABLE_W, first_chunk_h))

        story.append(Spacer(1, 12))

    doc.build(story)
    logger.info('[gerar_pdf_report] PDF gerado. job_id=%s path=%s', job_id, pdf_path)
    return str(pdf_path)
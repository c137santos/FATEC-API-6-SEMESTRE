import logging
import os
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

logger = logging.getLogger(__name__)

_OUTPUT_BASE = Path(
    os.getenv('REPORTS_DIR', str(Path(__file__).resolve().parent.parent.parent / 'output' / 'reports'))
)

_CHARTS = [
    ('grafico_tam', 'Top 10 Maiores Trechos (TAM)'),
    ('pt_pnt', 'Perdas Técnicas e Não Técnicas (PT x PNT)'),
    ('tabela_score', 'Score de Criticidade'),
    ('mapa_calor', 'Mapa de Calor de Criticidade'),
]


def _reports_dir(job_id: str) -> Path:
    path = _OUTPUT_BASE / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _placeholder_png(path: Path, title: str) -> None:
    """Saves a placeholder PNG when chart data is insufficient."""
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


def _scaled_image(img_path: Path, max_width: float) -> Image:
    reader = ImageReader(str(img_path))
    iw, ih = reader.getSize()
    aspect = ih / iw
    return Image(str(img_path), width=max_width, height=max_width * aspect)


def gerar_pdf_report(job_id: str, render_paths: dict, job_meta: dict) -> str:
    """
    Builds the consolidated PDF from image paths stored in render_paths.
    Returns the absolute path of the generated PDF.
    """
    out_dir = _reports_dir(job_id)
    pdf_path = out_dir / 'report.pdf'
    placeholder_dir = out_dir / 'placeholders'
    placeholder_dir.mkdir(exist_ok=True)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ReportTitle', parent=styles['Title'], fontSize=18, spaceAfter=10
    )
    meta_style = ParagraphStyle(
        'ReportMeta', parent=styles['Normal'], fontSize=9,
        textColor=colors.grey, spaceAfter=4,
    )
    section_style = ParagraphStyle(
        'ReportSection', parent=styles['Heading2'],
        fontSize=13, spaceBefore=16, spaceAfter=8,
    )

    dist_name = job_meta.get('dist_name', 'Distribuidora')
    ano = job_meta.get('ano_gdb', '')
    page_width = A4[0] - 3 * cm

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )

    story = [
        Paragraph(f'Relatório de Análise — {dist_name}', title_style),
        Paragraph(f'Ano: {ano} | Job ID: {job_id}', meta_style),
        Paragraph(
            f'Gerado em: {datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")}',
            meta_style,
        ),
        HRFlowable(width='100%', thickness=1, color=colors.lightgrey, spaceAfter=20),
    ]

    for key, section_title in _CHARTS:
        story.append(Paragraph(section_title, section_style))

        img_path_str = render_paths.get(key)
        img_path = Path(img_path_str) if img_path_str else None

        if not img_path or not img_path.exists():
            logger.info(
                '[gerar_pdf_report] Placeholder para %s. job_id=%s', key, job_id
            )
            img_path = placeholder_dir / f'placeholder_{key}.png'
            _placeholder_png(img_path, section_title)

        try:
            story.append(_scaled_image(img_path, page_width))
        except Exception:
            logger.warning(
                '[gerar_pdf_report] Falha ao incluir imagem %s, gerando placeholder. job_id=%s',
                key, job_id,
            )
            img_path = placeholder_dir / f'placeholder_{key}_err.png'
            _placeholder_png(img_path, section_title)
            story.append(_scaled_image(img_path, page_width))

        story.append(Spacer(1, 12))

    doc.build(story)
    logger.info('[gerar_pdf_report] PDF gerado. job_id=%s path=%s', job_id, pdf_path)
    return str(pdf_path)

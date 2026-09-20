"""
Export PDF d'un rapport de cycle simulé.

Utilise ReportLab si disponible. Si absent, REPORTLAB_AVAILABLE = False
et l'appel à export_cycle_report_pdf lèvera une RuntimeError explicite
(que l'UI doit attraper pour afficher un message clair à l'utilisateur).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List
from xml.sax.saxutils import escape

from app.model.constants import REPORT_COLUMNS, VARIABLES
from app.model.sterilization_model import Segment

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def build_cycle_report_rows(segments: List[Segment]) -> List[List[str]]:
    """Construit les lignes du tableau PDF (état moyen par phase)."""
    rows: List[List[str]] = []
    for segment in segments:
        representative_state: Dict[str, float] = {}
        for variable in VARIABLES:
            s = float(segment.start_state.get(variable, 0.0))
            e = float(segment.end_state.get(variable, 0.0))
            representative_state[variable] = (s + e) / 2.0
        row = [segment.name, f"{float(segment.duration):.2f}"]
        for _, vk in REPORT_COLUMNS[2:]:
            row.append(f"{representative_state.get(vk or '', 0.0):.2f}")
        rows.append(row)
    return rows


def export_cycle_report_pdf(
    pdf_path: str,
    recipe_name: str,
    segments: List[Segment],
    total_duration: float,
) -> None:
    """Génère un PDF A4 paysage avec le tableau des phases simulées."""
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError(
            "La bibliothèque 'reportlab' n'est pas installée. "
            "Installer avec : pip install reportlab"
        )

    styles = getSampleStyleSheet()
    table_data = [[c for c, _ in REPORT_COLUMNS],
                  *build_cycle_report_rows(segments)]

    doc = SimpleDocTemplate(
        str(Path(pdf_path)),
        pagesize=landscape(A4),
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )

    story = [
        Paragraph("Rapport de cycle simulé", styles["Title"]),
        Spacer(1, 5 * mm),
        Paragraph(f"Recette : {escape(recipe_name)}", styles["Normal"]),
        Paragraph(
            f"Durée totale : {total_duration:.2f} min "
            f"({total_duration/60.0:.2f} h)",
            styles["Normal"],
        ),
        Paragraph(f"Nombre de phases : {len(segments)}", styles["Normal"]),
        Spacer(1, 5 * mm),
    ]

    col_widths = [70*mm, 22*mm, 18*mm, 18*mm, 18*mm, 18*mm, 18*mm, 20*mm, 18*mm]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F6C8C")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.whitesmoke, colors.HexColor("#EAF2F6")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B8C7D1")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#7E94A1")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    doc.build(story)

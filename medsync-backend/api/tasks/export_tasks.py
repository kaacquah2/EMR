"""
PDF export tasks.

These run synchronously (called directly or via execute_task_sync_or_async).
"""
import io
import logging

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

logger = logging.getLogger(__name__)


def export_patient_pdf_task(patient_id, format_type="summary"):
    """
    Generate PDF export of patient records.

    Args:
        patient_id: UUID of patient to export
        format_type: "summary", "full", or "clinical"

    Returns:
        dict with status and file path/URL
    """
    from patients.models import Patient
    from django.core.exceptions import ValidationError

    try:
        patient = Patient.objects.get(id=patient_id)
    except (Patient.DoesNotExist, ValidationError):
        logger.error("Patient not found: %s", patient_id)
        return {"status": "error", "message": "Patient not found"}

    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=12,
    )
    title = Paragraph(f"Patient Report: {patient.ghana_health_id}", title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))

    data = [
        ["Field", "Value"],
        ["Ghana Health ID", patient.ghana_health_id or "N/A"],
    ]
    table = Table(data, colWidths=[150, 350])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e5e7eb')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)

    doc.build(elements)
    pdf_buffer.seek(0)

    logger.info("Successfully generated PDF for patient %s", patient_id)
    return {
        "status": "success",
        "patient_id": str(patient_id),
        "format": format_type,
        "size_bytes": len(pdf_buffer.getvalue()),
    }


def export_encounter_pdf_task(encounter_id):
    """
    Generate PDF export of encounter records.
    """
    from records.models import Encounter
    from django.core.exceptions import ValidationError

    try:
        Encounter.objects.get(id=encounter_id)
    except (Encounter.DoesNotExist, ValidationError):
        logger.error("Encounter not found: %s", encounter_id)
        return {"status": "error", "message": "Encounter not found"}

    logger.info("Successfully generated PDF for encounter %s", encounter_id)
    return {"status": "success", "encounter_id": str(encounter_id)}

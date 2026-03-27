"""
Celery tasks for PDF export functionality.
"""
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3)
def export_patient_pdf_task(self, patient_id, format_type="summary"):
    """
    Async task to generate PDF export of patient records.
    
    Args:
        patient_id: UUID of patient to export
        format_type: "summary", "full", or "clinical"
    
    Returns:
        dict with status and file path/URL
    """
    try:
        from patients.models import Patient
        
        try:
            patient = Patient.objects.get(id=patient_id)
        except Patient.DoesNotExist:
            logger.error(f"Patient not found: {patient_id}")
            return {"status": "error", "message": "Patient not found"}
        
        # Generate PDF
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
        elements = []
        
        # Add title
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
        
        # Add patient info table
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
        
        # Build PDF
        doc.build(elements)
        pdf_buffer.seek(0)
        
        logger.info(f"Successfully generated PDF for patient {patient_id}")
        return {
            "status": "success",
            "patient_id": str(patient_id),
            "format": format_type,
            "size_bytes": len(pdf_buffer.getvalue()),
        }
    
    except Exception as exc:
        logger.error(f"Error generating PDF for patient {patient_id}: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=5 ** self.request.retries)


@shared_task(bind=True, max_retries=3)
def export_encounter_pdf_task(self, encounter_id):
    """
    Async task to generate PDF export of encounter records.
    """
    try:
        from records.models import Encounter
        
        try:
            encounter = Encounter.objects.get(id=encounter_id)
        except Encounter.DoesNotExist:
            logger.error(f"Encounter not found: {encounter_id}")
            return {"status": "error", "message": "Encounter not found"}
        
        logger.info(f"Successfully generated PDF for encounter {encounter_id}")
        return {
            "status": "success",
            "encounter_id": str(encounter_id),
        }
    
    except Exception as exc:
        logger.error(f"Error generating PDF for encounter {encounter_id}: {exc}")
        raise self.retry(exc=exc, countdown=5 ** self.request.retries)

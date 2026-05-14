"""
Django signals for Clinical Decision Support (CDS) engine.

Auto-fires CDS rule evaluation when Prescription or Diagnosis is created.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from records.models import Prescription, Diagnosis, Encounter
from api.services.cds_engine import RulesEngine

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Prescription)
def prescription_created_trigger_cds(sender, instance: Prescription, created: bool, **kwargs):
    """
    Trigger CDS evaluation when a prescription is created.
    
    Evaluates all clinical rules and creates CdsAlert records if needed.
    """
    if not created:
        # Only run on creation, not on updates
        return
    
    if not instance.patient or not instance.hospital:
        # Skip if incomplete prescription
        logger.debug(f"Skipping CDS for incomplete prescription {instance.id}")
        return
    
    try:
        # Find the encounter associated with this prescription
        # Assumption: prescription is created within an encounter context
        encounter = None
        
        # Try to get encounter from the record's encounter relationship
        if hasattr(instance, 'record') and hasattr(instance.record, 'encounter'):
            encounter = instance.record.encounter
        
        if not encounter:
            # Fall back: get latest encounter for this patient
            encounter = Encounter.objects.filter(
                patient=instance.patient,
                hospital=instance.hospital
            ).order_by('-created_at').first()
        
        if not encounter:
            logger.warning(f"No encounter found for prescription {instance.id}")
            return
        
        # Evaluate all CDS rules
        alerts = RulesEngine.evaluate_prescription(
            prescription=instance,
            encounter_id=str(encounter.id),
            patient=instance.patient
        )
        
        # Save alerts to database
        for alert in alerts:
            alert.save()
            logger.info(f"Created CDS alert: {alert.rule.name} for prescription {instance.id}")
        
        if alerts:
            logger.debug(f"CDS engine created {len(alerts)} alerts for prescription {instance.id}")
    
    except Exception as e:
        logger.error(f"Error in CDS signal for prescription {instance.id}: {e}", exc_info=True)
        # Don't re-raise; signals shouldn't break normal flow


@receiver(post_save, sender=Diagnosis)
def diagnosis_created_trigger_cds(sender, instance: Diagnosis, created: bool, **kwargs):
    """
    Trigger CDS evaluation when a diagnosis is created.
    
    Evaluates all clinical rules and creates CdsAlert records if needed.
    """
    if not created:
        # Only run on creation, not on updates
        return
    
    # Get the patient and encounter from the diagnosis's related medical record
    if not hasattr(instance, 'record') or not instance.record:
        logger.warning(f"Diagnosis {instance.id} has no associated MedicalRecord")
        return
    
    record = instance.record
    patient = record.patient
    hospital = record.patient.registered_at  # Assuming patient has registered_at pointing to hospital
    
    if not patient or not hospital:
        logger.debug(f"Skipping CDS for incomplete diagnosis {instance.id}")
        return
    
    try:
        # Find the encounter associated with this diagnosis
        encounter = None
        
        # Try to get encounter from the record's encounter relationship
        if hasattr(record, 'encounter'):
            encounter = record.encounter
        
        if not encounter:
            # Fall back: get latest encounter for this patient
            encounter = Encounter.objects.filter(
                patient=patient,
                hospital=hospital
            ).order_by('-created_at').first()
        
        if not encounter:
            logger.warning(f"No encounter found for diagnosis {instance.id}")
            return
        
        # Evaluate all CDS rules
        alerts = RulesEngine.evaluate_diagnosis(
            diagnosis=instance,
            encounter_id=str(encounter.id),
            patient=patient
        )
        
        # Save alerts to database
        for alert in alerts:
            alert.save()
            logger.info(f"Created CDS alert: {alert.rule.name} for diagnosis {instance.id}")
        
        if alerts:
            logger.debug(f"CDS engine created {len(alerts)} alerts for diagnosis {instance.id}")
    
    except Exception as e:
        logger.error(f"Error in CDS signal for diagnosis {instance.id}: {e}", exc_info=True)
        # Don't re-raise; signals shouldn't break normal flow

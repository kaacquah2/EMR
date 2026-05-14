"""
AI System Status Endpoint for MedSync.

Provides a single source of truth for the current state of the AI
subsystem — model readiness, monitoring health, and clinical validation
status. Designed to make the demo-only nature impossible to miss.
"""

import logging
from datetime import datetime
from typing import Dict, Any

from django.core.cache import cache

logger = logging.getLogger(__name__)


def get_ai_system_status() -> Dict[str, Any]:
    """
    Get comprehensive AI system status.

    Returns a report covering:
    - Overall system readiness (DEMONSTRATION_ONLY / PRODUCTION_READY)
    - Per-model validation status
    - Monitoring health
    - Clinical validation checklist progress
    - What's needed for production
    """
    from api.ai.clinical_validation import (
        MODEL_VALIDATION_REGISTRY,
        ClinicalValidationChecklist,
        get_clinical_disclaimer,
        ReadinessLevel,
        READINESS_LABELS,
    )

    # Per-model status
    models_status = {}
    max_readiness = ReadinessLevel.UNVALIDATED

    for model_name, record in MODEL_VALIDATION_REGISTRY.items():
        models_status[model_name] = {
            'name': record.model_name,
            'version': record.model_version,
            'readiness_level': record.readiness_level.value,
            'readiness_label': READINESS_LABELS[record.readiness_level],
            'data_sources': [ds.source_name for ds in record.data_sources],
            'limitations_count': len(record.known_limitations),
            'top_limitation': record.known_limitations[0] if record.known_limitations else None,
        }
        max_readiness = max(max_readiness, record.readiness_level)

    # Monitoring health (from latest report, if available)
    monitoring_report = cache.get('ai_monitoring_report_latest')
    monitoring_health = 'UNKNOWN'
    if monitoring_report:
        monitoring_health = monitoring_report.get('overall_health', 'UNKNOWN')

    # Clinical validation checklist
    validation_status = ClinicalValidationChecklist.get_status()

    # Overall system readiness
    if max_readiness <= ReadinessLevel.SYNTHETIC_ONLY:
        overall_readiness = 'DEMONSTRATION_ONLY'
    elif max_readiness <= ReadinessLevel.PUBLIC_DATASET:
        overall_readiness = 'RESEARCH_ONLY'
    elif max_readiness <= ReadinessLevel.RETROSPECTIVE_CLINICAL:
        overall_readiness = 'INVESTIGATIONAL'
    elif max_readiness <= ReadinessLevel.PROSPECTIVE_CLINICAL:
        overall_readiness = 'PENDING_APPROVAL'
    else:
        overall_readiness = 'PRODUCTION_READY'

    return {
        'system_readiness': overall_readiness,
        'disclaimer': get_clinical_disclaimer(),
        'demo_mode': overall_readiness != 'PRODUCTION_READY',
        'models': models_status,
        'monitoring': {
            'health': monitoring_health,
            'last_report': monitoring_report.get('generated_at') if monitoring_report else None,
        },
        'clinical_validation': {
            'status': validation_status['overall_status'],
            'completion_pct': validation_status['completion_pct'],
            'critical_incomplete': validation_status['critical_incomplete'],
        },
        'production_blockers': _get_production_blockers(validation_status),
        'generated_at': datetime.now().isoformat(),
    }


def _get_production_blockers(validation_status: Dict) -> list:
    """Extract critical blockers preventing production deployment."""
    blockers = []
    for req in validation_status.get('requirements', []):
        if req['priority'] == 'CRITICAL' and req['status'] != 'COMPLETED':
            blockers.append({
                'id': req['id'],
                'requirement': req['requirement'],
                'notes': req.get('notes', ''),
            })
    return blockers

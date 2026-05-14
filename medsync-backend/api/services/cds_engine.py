"""
Clinical Decision Support (CDS) Rules Engine

Evaluates clinical rules on prescription/diagnosis creation.
Checks for:
- Drug-drug interactions
- Drug-allergy contraindications
- Renal dose adjustments
- Duplicate therapy
"""

import json
import os
import logging
from typing import List, Optional, Dict, Any
from django.utils import timezone
from django.db.models import Q
from records.models import Prescription, Diagnosis, Vital, LabResult
from patients.models import Patient
from api.models import ClinicalRule, CdsAlert

logger = logging.getLogger(__name__)


class RulesEngine:
    """Evaluates clinical rules and generates alerts."""
    
    # Cache rules in memory to avoid constant DB hits
    _rules_cache = None
    _cache_timestamp = None
    _CACHE_TTL = 3600  # 1 hour
    
    # Load drug interaction dataset once
    _drug_interactions = None
    
    @classmethod
    def _load_drug_interactions(cls):
        """Load drug interaction dataset from JSON."""
        if cls._drug_interactions is not None:
            return cls._drug_interactions
        
        try:
            fixture_path = os.path.join(
                os.path.dirname(__file__), '..', 'drug_interactions.json'
            )
            with open(fixture_path, 'r') as f:
                data = json.load(f)
                cls._drug_interactions = data.get('interactions', [])
        except Exception as e:
            logger.error(f"Failed to load drug interactions: {e}")
            cls._drug_interactions = []
        
        return cls._drug_interactions
    
    @classmethod
    def _get_active_rules(cls, rule_type: str = None) -> List[ClinicalRule]:
        """Get active rules from cache or DB."""
        from django.utils import timezone as tz
        
        now = tz.now().timestamp()
        
        # Refresh cache if expired
        if (cls._rules_cache is None or 
            cls._cache_timestamp is None or
            (now - cls._cache_timestamp) > cls._CACHE_TTL):
            
            query = ClinicalRule.objects.filter(active=True)
            if rule_type:
                query = query.filter(rule_type=rule_type)
            
            cls._rules_cache = list(query)
            cls._cache_timestamp = now
        
        if rule_type:
            return [r for r in cls._rules_cache if r.rule_type == rule_type]
        return cls._rules_cache
    
    @classmethod
    def evaluate_prescription(
        cls, 
        prescription: Prescription,
        encounter_id: str,
        patient: Patient
    ) -> List[CdsAlert]:
        """
        Evaluate all rules for a new prescription.
        
        Returns list of CdsAlert objects (not yet saved).
        """
        from records.models import Encounter
        
        try:
            encounter = Encounter.objects.get(id=encounter_id)
        except Encounter.DoesNotExist:
            logger.error(f"Encounter {encounter_id} not found")
            return []
        
        alerts = []
        
        # Check drug-drug interactions
        alerts.extend(cls._check_drug_interactions(prescription, patient, encounter))
        
        # Check drug-allergy contraindications
        alerts.extend(cls._check_drug_allergy(prescription, patient, encounter))
        
        # Check renal dosing
        alerts.extend(cls._check_renal_dosing(prescription, patient, encounter))
        
        # Check duplicate therapy
        alerts.extend(cls._check_duplicate_therapy(prescription, patient, encounter))
        
        return alerts
    
    @classmethod
    def evaluate_diagnosis(
        cls,
        diagnosis: Diagnosis,
        encounter_id: str,
        patient: Patient
    ) -> List[CdsAlert]:
        """
        Evaluate all rules for a new diagnosis.
        
        Currently diagnosis checks are minimal, but framework supports expansion.
        """
        # Placeholder for diagnosis-specific rules
        # Could add: comorbidity checks, age-appropriate diagnosis validation, etc.
        return []
    
    @classmethod
    def _check_drug_interactions(
        cls,
        prescription: Prescription,
        patient: Patient,
        encounter
    ) -> List[CdsAlert]:
        """Check for drug-drug interactions with existing prescriptions."""
        alerts = []
        new_drug = prescription.drug_name.lower().strip()
        
        # Load interaction dataset
        interactions = cls._load_drug_interactions()
        
        # Get active prescriptions for this patient from encounters in last 30 days
        from django.db.models import Prefetch
        from django.utils.timezone import now, timedelta
        
        last_30_days = now() - timedelta(days=30)
        existing_prescriptions = Prescription.objects.filter(
            patient=patient,
            created_at__gte=last_30_days,
            dispense_status__in=['pending', 'dispensed']
        ).exclude(id=prescription.id)
        
        for existing_rx in existing_prescriptions:
            existing_drug = existing_rx.drug_name.lower().strip()
            
            # Check both directions of interaction
            for interaction in interactions:
                d1 = interaction['drug1'].lower()
                d2 = interaction['drug2'].lower()
                
                # Match interaction pairs in either direction
                if (d1 in new_drug or new_drug in d1) and (d2 in existing_drug or existing_drug in d2):
                    alert = cls._create_alert_from_interaction(
                        prescription, existing_rx, interaction, encounter, 'drug_interaction'
                    )
                    if alert:
                        alerts.append(alert)
                    break
                elif (d2 in new_drug or new_drug in d2) and (d1 in existing_drug or existing_drug in d1):
                    alert = cls._create_alert_from_interaction(
                        prescription, existing_rx, interaction, encounter, 'drug_interaction'
                    )
                    if alert:
                        alerts.append(alert)
                    break
        
        return alerts
    
    @classmethod
    def _check_drug_allergy(
        cls,
        prescription: Prescription,
        patient: Patient,
        encounter
    ) -> List[CdsAlert]:
        """Check if prescribed drug conflicts with patient allergies."""
        alerts = []
        
        # Try to access patient allergies
        # Assumption: Patient has an allergy_list or allergies relation
        try:
            # Try common allergy relationship names
            allergies = []
            
            if hasattr(patient, 'allergy_list'):
                allergies = patient.allergy_list if patient.allergy_list else []
            elif hasattr(patient, 'allergies'):
                allergies = list(patient.allergies.all())
            
            if not allergies:
                return alerts
            
            new_drug = prescription.drug_name.lower().strip()
            
            # Simple substring matching for allergy conflicts
            # Could be enhanced with drug family/class mappings
            allergy_classes = {
                'penicillin': ['amoxicillin', 'ampicillin', 'amoxicillin-clavulanate', 'penicillin'],
                'sulfa': ['sulfamethoxazole', 'trimethoprim-sulfamethoxazole', 'sulfadiazine'],
                'nsaid': ['ibuprofen', 'naproxen', 'indomethacin', 'ketorolac'],
                'ace_inhibitor': ['lisinopril', 'enalapril', 'ramipril', 'captopril'],
            }
            
            for allergy in allergies:
                allergy_name = str(allergy).lower() if allergy else ""
                
                # Direct match
                if allergy_name in new_drug or new_drug in allergy_name:
                    rule = cls._get_or_create_rule('drug_allergy', 'critical')
                    alert = CdsAlert(
                        encounter=encounter,
                        rule=rule,
                        prescription=prescription,
                        severity='critical',
                        message=f"⚠️ CONTRAINDICATION: Patient has documented allergy to {allergy}. Drug prescribed: {prescription.drug_name}",
                        context_data={
                            'allergy': str(allergy),
                            'drug': prescription.drug_name,
                        }
                    )
                    alerts.append(alert)
                    break
                
                # Class-based match
                for family, drugs in allergy_classes.items():
                    if allergy_name in family or family in allergy_name:
                        for drug in drugs:
                            if drug in new_drug or new_drug in drug:
                                rule = cls._get_or_create_rule('drug_allergy', 'critical')
                                alert = CdsAlert(
                                    encounter=encounter,
                                    rule=rule,
                                    prescription=prescription,
                                    severity='critical',
                                    message=f"⚠️ CONTRAINDICATION: Patient is allergic to {allergy} (class: {family}). Prescribed drug {prescription.drug_name} is in same class.",
                                    context_data={
                                        'allergy': str(allergy),
                                        'drug_class': family,
                                        'drug': prescription.drug_name,
                                    }
                                )
                                alerts.append(alert)
                                break
        except Exception as e:
            logger.warning(f"Error checking allergies for patient {patient.id}: {e}")
        
        return alerts
    
    @classmethod
    def _check_renal_dosing(
        cls,
        prescription: Prescription,
        patient: Patient,
        encounter
    ) -> List[CdsAlert]:
        """Check if dosage needs adjustment based on renal function."""
        alerts = []
        
        # Drugs that require renal dose adjustment
        renal_sensitive_drugs = {
            'metformin': {'threshold_egfr': 45, 'adjustment': 'Reduce dose or discontinue if eGFR < 45'},
            'lisinopril': {'threshold_egfr': 30, 'adjustment': 'Reduce dose if eGFR < 30'},
            'digoxin': {'threshold_egfr': 30, 'adjustment': 'Reduce dose if eGFR < 30'},
            'gentamicin': {'threshold_egfr': 30, 'adjustment': 'Extend dosing interval if eGFR < 30'},
            'acyclovir': {'threshold_egfr': 50, 'adjustment': 'Adjust dose based on eGFR'},
            'amoxicillin': {'threshold_egfr': 30, 'adjustment': 'Increase dosing interval if eGFR < 30'},
        }
        
        drug_lower = prescription.drug_name.lower().strip()
        
        # Check if drug requires renal dosing
        matching_drug = None
        for drug_name, dosing_info in renal_sensitive_drugs.items():
            if drug_name in drug_lower or drug_lower in drug_name:
                matching_drug = (drug_name, dosing_info)
                break
        
        if not matching_drug:
            return alerts
        
        drug_name, dosing_info = matching_drug
        
        # Try to get latest creatinine or eGFR value
        try:
            # Look for lab results or vitals with eGFR or creatinine in last 30 days
            from django.utils.timezone import now, timedelta
            
            last_30_days = now() - timedelta(days=30)
            
            egfr = None
            creatinine = None
            
            # Try LabResult
            try:
                latest_lab = LabResult.objects.filter(
                    patient=patient,
                    created_at__gte=last_30_days
                ).order_by('-created_at').first()
                
                if latest_lab and hasattr(latest_lab, 'value'):
                    # Try to parse as eGFR or creatinine
                    if hasattr(latest_lab, 'test_type'):
                        test_type = str(latest_lab.test_type).lower()
                        if 'egfr' in test_type or 'gfr' in test_type:
                            egfr = float(latest_lab.value) if latest_lab.value else None
                        elif 'creatinine' in test_type:
                            creatinine = float(latest_lab.value) if latest_lab.value else None
            except Exception:
                pass
            
            # Try Vital
            try:
                if not egfr and not creatinine:
                    latest_vital = Vital.objects.filter(
                        patient=patient,
                        created_at__gte=last_30_days
                    ).order_by('-created_at').first()
                    
                    if latest_vital:
                        if hasattr(latest_vital, 'egfr') and latest_vital.egfr:
                            egfr = float(latest_vital.egfr)
                        elif hasattr(latest_vital, 'creatinine_mg_dl') and latest_vital.creatinine_mg_dl:
                            creatinine = float(latest_vital.creatinine_mg_dl)
            except Exception:
                pass
            
            # If we have eGFR and it's below threshold, alert
            if egfr is not None and egfr < dosing_info['threshold_egfr']:
                rule = cls._get_or_create_rule('renal_dosing', 'warning')
                alert = CdsAlert(
                    encounter=encounter,
                    rule=rule,
                    prescription=prescription,
                    severity='warning',
                    message=f"⚠️ RENAL DOSE ADJUSTMENT: {prescription.drug_name} requires adjustment for renal impairment (eGFR {egfr:.1f}). {dosing_info['adjustment']}",
                    context_data={
                        'drug': prescription.drug_name,
                        'egfr': egfr,
                        'threshold': dosing_info['threshold_egfr'],
                        'adjustment': dosing_info['adjustment'],
                    }
                )
                alerts.append(alert)
        
        except Exception as e:
            logger.warning(f"Error checking renal dosing for patient {patient.id}: {e}")
        
        return alerts
    
    @classmethod
    def _check_duplicate_therapy(
        cls,
        prescription: Prescription,
        patient: Patient,
        encounter
    ) -> List[CdsAlert]:
        """Check for duplicate therapy (same drug class prescribed twice)."""
        alerts = []
        
        # Drug class mappings (ATC-inspired)
        drug_classes = {
            'statin': ['atorvastatin', 'simvastatin', 'pravastatin', 'rosuvastatin', 'lovastatin'],
            'ace_inhibitor': ['lisinopril', 'enalapril', 'ramipril', 'captopril', 'perindopril'],
            'beta_blocker': ['metoprolol', 'propranolol', 'atenolol', 'bisoprolol', 'carvedilol'],
            'nsaid': ['ibuprofen', 'naproxen', 'indomethacin', 'ketorolac', 'meloxicam'],
            'antibiotic_aminoglycoside': ['gentamicin', 'tobramycin', 'amikacin', 'netilmicin'],
            'antibiotic_cephalosporin': ['cefixime', 'ceftriaxone', 'cefazolin', 'cephalexin'],
        }
        
        new_drug_lower = prescription.drug_name.lower().strip()
        
        # Find drug class for new prescription
        new_drug_class = None
        for drug_class, drugs in drug_classes.items():
            for drug in drugs:
                if drug in new_drug_lower or new_drug_lower in drug:
                    new_drug_class = drug_class
                    break
            if new_drug_class:
                break
        
        if not new_drug_class:
            return alerts
        
        # Check for other drugs in same class in last 7 days
        from django.utils.timezone import now, timedelta
        
        last_7_days = now() - timedelta(days=7)
        existing_prescriptions = Prescription.objects.filter(
            patient=patient,
            created_at__gte=last_7_days,
            dispense_status__in=['pending', 'dispensed']
        ).exclude(id=prescription.id)
        
        for existing_rx in existing_prescriptions:
            existing_drug_lower = existing_rx.drug_name.lower().strip()
            
            # Check if existing prescription is in same drug class
            for drug_class, drugs in drug_classes.items():
                if drug_class == new_drug_class:
                    for drug in drugs:
                        if drug in existing_drug_lower or existing_drug_lower in drug:
                            rule = cls._get_or_create_rule('duplicate_therapy', 'info')
                            alert = CdsAlert(
                                encounter=encounter,
                                rule=rule,
                                prescription=prescription,
                                severity='info',
                                message=f"ℹ️ DUPLICATE THERAPY: Patient already taking {existing_rx.drug_name} ({drug_class}). New prescription: {prescription.drug_name}. Confirm intentional.",
                                context_data={
                                    'drug_class': drug_class,
                                    'existing_drug': existing_rx.drug_name,
                                    'new_drug': prescription.drug_name,
                                }
                            )
                            alerts.append(alert)
                            return alerts  # Only report once per class
        
        return alerts
    
    @classmethod
    def _create_alert_from_interaction(
        cls,
        new_prescription: Prescription,
        existing_prescription: Prescription,
        interaction: Dict[str, Any],
        encounter,
        rule_type: str
    ) -> Optional[CdsAlert]:
        """Create an alert from an interaction record."""
        try:
            severity = interaction.get('severity', 'warning')
            rule = cls._get_or_create_rule(rule_type, severity)
            
            alert = CdsAlert(
                encounter=encounter,
                rule=rule,
                prescription=new_prescription,
                severity=severity,
                message=f"⚠️ DRUG INTERACTION: {new_prescription.drug_name} + {existing_prescription.drug_name}. {interaction.get('description', '')}. Action: {interaction.get('action', '')}",
                context_data={
                    'drug1': new_prescription.drug_name,
                    'drug2': existing_prescription.drug_name,
                    'description': interaction.get('description', ''),
                    'action': interaction.get('action', ''),
                }
            )
            return alert
        except Exception as e:
            logger.error(f"Error creating alert from interaction: {e}")
            return None
    
    @classmethod
    def _get_or_create_rule(cls, rule_type: str, severity: str) -> ClinicalRule:
        """Get or create a generic rule for the given type and severity."""
        try:
            rule = ClinicalRule.objects.filter(
                rule_type=rule_type,
                severity=severity,
                active=True
            ).first()
            
            if rule:
                return rule
            
            # Create a default rule if not found
            rule_name_map = {
                'drug_interaction': f'Drug-Drug Interaction ({severity})',
                'drug_allergy': f'Drug-Allergy Contraindication ({severity})',
                'renal_dosing': f'Renal Dose Adjustment ({severity})',
                'duplicate_therapy': f'Duplicate Therapy ({severity})',
            }
            
            rule = ClinicalRule.objects.create(
                name=rule_name_map.get(rule_type, f'Rule: {rule_type} ({severity})'),
                rule_type=rule_type,
                severity=severity,
                active=True,
                description=f"Auto-generated {rule_type} rule"
            )
            return rule
        except Exception as e:
            logger.error(f"Error getting/creating rule: {e}")
            # Return a minimal rule-like object
            raise

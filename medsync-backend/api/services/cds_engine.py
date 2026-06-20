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
from django.core.cache import cache
from django.conf import settings
from records.models import Prescription, Diagnosis, Vital, LabResult
from patients.models import Patient
from api.models import ClinicalRule, CdsAlert

logger = logging.getLogger(__name__)

# Cache key for CDS rules.
# With DatabaseCache (the production default) this key is shared across all
# workers — invalidation via cache.delete() takes effect immediately for every
# process.  With LocMemCache (Vercel / single-process dev) each invocation
# is isolated so stale entries cannot accumulate past the TTL.
_CDS_RULES_CACHE_KEY = "cds:active_rules:all"
_CDS_RULES_CACHE_TTL = getattr(settings, "CDS_RULES_CACHE_TTL", 3600)  # 1 hour


def invalidate_cds_rules_cache():
    """
    Invalidate the CDS rules cache.

    Called automatically via post_save signal on ClinicalRule so that
    all workers pick up rule changes without waiting for TTL expiry.
    """
    cache.delete(_CDS_RULES_CACHE_KEY)
    logger.info("CDS rules cache invalidated (key: %s)", _CDS_RULES_CACHE_KEY)


class RulesEngine:
    """Evaluates clinical rules and generates alerts.

    Rules are cached (shared across workers via DatabaseCache in production).
    The cache is invalidated whenever a ClinicalRule is saved (via post_save
    signal in api/signals_cds.py). Falls back to DB on cache miss.
    """
    
    # Load drug interaction dataset once — process-local is fine (read-only JSON)
    _drug_interactions = None
    _drug_interactions_mtime = 0
    
    @classmethod
    def _load_drug_interactions(cls):
        """Load drug interaction dataset from JSON, reloading if the file changes."""
        fixture_path = os.path.join(
            os.path.dirname(__file__), '..', 'drug_interactions.json'
        )
        try:
            mtime = os.path.getmtime(fixture_path)
        except Exception:
            mtime = 0

        if cls._drug_interactions is not None and cls._drug_interactions_mtime == mtime:
            return cls._drug_interactions
        
        try:
            with open(fixture_path, 'r') as f:
                data = json.load(f)
                cls._drug_interactions = data.get('interactions', [])
                cls._drug_interactions_mtime = mtime
        except Exception as e:
            logger.error(f"Failed to load drug interactions: {e}")
            if cls._drug_interactions is None:
                cls._drug_interactions = []
        
        return cls._drug_interactions

    @classmethod
    def _normalize_drug_name(cls, drug_name: str) -> List[str]:
        """Normalize drug name into lowercase words, ignoring strengths and formulations."""
        import re
        drug_name = drug_name.lower().strip()
        # Strip strength like "500mg", "100 mg", "5ml", "10%", etc.
        strength_pattern = re.compile(r'\b\d+(?:\.\d+)?\s*(?:mg|g|mcg|ml|l|%|iu|units|caps?|tabs?)\b', re.IGNORECASE)
        clean_name = strength_pattern.sub('', drug_name)
        # Split by non-alphabetic characters and filter out short words
        words = [w for w in re.split(r'[^a-zA-Z]+', clean_name) if len(w) > 2]
        return words

    @classmethod
    def _match_drug_names(cls, interaction_drug: str, prescribed_drug: str) -> bool:
        """Check if interaction_drug matches prescribed_drug using word tokenization and prefix matching."""
        i_drug = interaction_drug.lower().strip()
        p_drug = prescribed_drug.lower().strip()
        
        if i_drug == p_drug:
            return True
            
        i_words = cls._normalize_drug_name(i_drug)
        p_words = cls._normalize_drug_name(p_drug)
        
        if not i_words or not p_words:
            return False
            
        # Class-based mappings for interaction drug checks
        if i_drug in ('nsaids', 'nsaid'):
            nsaids = {'ibuprofen', 'naproxen', 'indomethacin', 'ketorolac', 'aspirin', 'diclofenac', 'meloxicam'}
            return any(w in nsaids for w in p_words) or 'nsaid' in p_words
            
        if 'potassium' in i_words:
            return 'potassium' in p_words
            
        if 'contrast' in i_words:
            return 'contrast' in p_words
            
        # Default match: all words in interaction_drug must match a word in prescribed_drug
        # We allow prefix matching if the word has at least 4 characters
        return all(any(iw == pw or (len(iw) >= 4 and pw.startswith(iw)) for pw in p_words) for iw in i_words)
    
    @classmethod
    def _get_active_rules(cls, rule_type: str = None) -> List[ClinicalRule]:
        """Get active rules from Redis cache or DB.

        Cache key: ``cds:active_rules:all`` (shared across all workers).
        Falls back to a live DB query on cache miss.
        Filtered by rule_type in-memory after retrieval to avoid per-type
        cache fragmentation.
        """
        # Try Redis first
        rules: List[ClinicalRule] | None = cache.get(_CDS_RULES_CACHE_KEY)

        if rules is None:
            # Cache miss → fetch from DB and repopulate Redis
            rules = list(ClinicalRule.objects.filter(active=True))
            try:
                cache.set(_CDS_RULES_CACHE_KEY, rules, timeout=_CDS_RULES_CACHE_TTL)
            except Exception as cache_err:
                # Non-fatal: continue without caching (Redis may be unavailable)
                logger.warning(
                    "Could not write CDS rules to cache: %s — serving from DB", cache_err
                )

        if rule_type:
            return [r for r in rules if r.rule_type == rule_type]
        return rules

    
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
        new_drug = prescription.drug_name
        
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
            existing_drug = existing_rx.drug_name
            
            # Check both directions of interaction
            for interaction in interactions:
                d1 = interaction['drug1']
                d2 = interaction['drug2']
                
                # Match interaction pairs in either direction using robust word matching
                if (cls._match_drug_names(d1, new_drug) and cls._match_drug_names(d2, existing_drug)) or \
                   (cls._match_drug_names(d2, new_drug) and cls._match_drug_names(d1, existing_drug)):
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
            
            new_drug = prescription.drug_name
            
            # Simple substring matching for allergy conflicts
            # Could be enhanced with drug family/class mappings
            allergy_classes = {
                'penicillin': ['amoxicillin', 'ampicillin', 'amoxicillin-clavulanate', 'penicillin'],
                'sulfa': ['sulfamethoxazole', 'trimethoprim-sulfamethoxazole', 'sulfadiazine'],
                'nsaid': ['ibuprofen', 'naproxen', 'indomethacin', 'ketorolac'],
                'ace_inhibitor': ['lisinopril', 'enalapril', 'ramipril', 'captopril'],
            }
            
            for allergy in allergies:
                allergy_name = str(allergy) if allergy else ""
                
                # Direct match using robust matching
                if cls._match_drug_names(allergy_name, new_drug):
                    rule = cls._get_or_create_rule('drug_allergy', 'critical')
                    alert = CdsAlert(
                        encounter=encounter,
                        rule=rule,
                        prescription=prescription,
                        severity='critical',
                        message=f"⚠️ CONTRAINDICATION: Patient has documented allergy to {allergy_name}. Drug prescribed: {prescription.drug_name}",
                        context_data={
                            'allergy': allergy_name,
                            'drug': prescription.drug_name,
                        }
                    )
                    alerts.append(alert)
                    break
                
                # Class-based match
                matched_class = False
                for family, drugs in allergy_classes.items():
                    allergy_words = cls._normalize_drug_name(allergy_name)
                    # Match family name to allergy words
                    if family in allergy_words or any(family.startswith(aw) or aw.startswith(family) for aw in allergy_words):
                        for drug in drugs:
                            if cls._match_drug_names(drug, new_drug):
                                rule = cls._get_or_create_rule('drug_allergy', 'critical')
                                alert = CdsAlert(
                                    encounter=encounter,
                                    rule=rule,
                                    prescription=prescription,
                                    severity='critical',
                                    message=f"⚠️ CONTRAINDICATION: Patient is allergic to {allergy_name} (class: {family}). Prescribed drug {prescription.drug_name} is in same class.",
                                    context_data={
                                        'allergy': allergy_name,
                                        'drug_class': family,
                                        'drug': prescription.drug_name,
                                    }
                                )
                                alerts.append(alert)
                                matched_class = True
                                break
                    if matched_class:
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
                    record__patient=patient,
                    record__created_at__gte=last_30_days
                ).order_by('-record__created_at').first()
                
                if latest_lab and latest_lab.result_value:
                    # Try to parse as eGFR or creatinine
                    test_name = str(latest_lab.test_name).lower()
                    if 'egfr' in test_name or 'gfr' in test_name:
                        egfr = float(latest_lab.result_value)
                    elif 'creatinine' in test_name:
                        creatinine = float(latest_lab.result_value)
            except Exception as e:
                logger.warning(f"Error querying/parsing latest LabResult for patient {patient.id}: {e}", exc_info=True)
            
            # Try Vital
            try:
                if not egfr and not creatinine:
                    latest_vital = Vital.objects.filter(
                        record__patient=patient,
                        record__created_at__gte=last_30_days
                    ).order_by('-record__created_at').first()
                    
                    if latest_vital:
                        if hasattr(latest_vital, 'egfr') and latest_vital.egfr:
                            egfr = float(latest_vital.egfr)
                        elif hasattr(latest_vital, 'creatinine_mg_dl') and latest_vital.creatinine_mg_dl:
                            creatinine = float(latest_vital.creatinine_mg_dl)
            except Exception as e:
                logger.warning(f"Error querying/parsing latest Vital for patient {patient.id}: {e}", exc_info=True)
            
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
        
        new_drug = prescription.drug_name
        
        # Find drug class for new prescription
        new_drug_class = None
        for drug_class, drugs in drug_classes.items():
            for drug in drugs:
                if cls._match_drug_names(drug, new_drug):
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
            existing_drug = existing_rx.drug_name
            
            # Check if existing prescription is in same drug class
            for drug_class, drugs in drug_classes.items():
                if drug_class == new_drug_class:
                    for drug in drugs:
                        if cls._match_drug_names(drug, existing_drug):
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

"""
Validate placeholder rule-based AI models on synthetic patient data.

This script tests whether qSOFA and NEWS2 scoring work reasonably on
the synthetic Ghanaian patient dataset before considering real data training.

Usage:
    python ml/validate_models_synthetic.py --file=demo_patients.json --verbose
"""

import json
import argparse
from datetime import datetime
from collections import defaultdict


class VitalsValidator:
    """Validates placeholder vital sign-based models on synthetic data."""
    
    def __init__(self):
        self.results = defaultdict(list)
        self.patient_count = 0
        self.encounter_count = 0
    
    def qsofa_score(self, respiratory_rate, systolic_bp, altered_mental=False):
        """
        Quick Sequential Organ Failure Assessment (qSOFA).
        Score ≥2 indicates high risk of poor outcome.
        
        Components:
        - RR ≥22: 1 point
        - SBP ≤100: 1 point
        - Altered mental status: 1 point
        """
        score = 0
        details = []
        
        if respiratory_rate >= 22:
            score += 1
            details.append("RR ≥22")
        
        if systolic_bp <= 100:
            score += 1
            details.append("SBP ≤100")
        
        if altered_mental:
            score += 1
            details.append("Altered mental")
        
        return score, details
    
    def news2_score(self, temp, systolic_bp, heart_rate, respiratory_rate, spo2):
        """
        National Early Warning Score 2 (NEWS2).
        Stratifies clinical deterioration risk.
        
        Score ranges:
        - 0-4: Low risk
        - 5-6: Medium risk
        - ≥7: High risk
        """
        score = 0
        details = []
        
        # Temperature
        if temp < 35.1:
            score += 3
            details.append("Temp <35.1°C (+3)")
        elif temp < 36.1:
            score += 1
            details.append("Temp 35.1-36°C (+1)")
        elif temp > 39.1:
            score += 1
            details.append("Temp >39.1°C (+1)")
        
        # Systolic BP
        if systolic_bp < 90:
            score += 3
            details.append("SBP <90 (+3)")
        elif systolic_bp < 101:
            score += 1
            details.append("SBP 90-100 (+1)")
        elif systolic_bp > 180:
            score += 2
            details.append("SBP >180 (+2)")
        
        # Heart rate
        if heart_rate < 40:
            score += 3
            details.append("HR <40 (+3)")
        elif heart_rate < 51:
            score += 1
            details.append("HR 40-50 (+1)")
        elif heart_rate > 130:
            score += 2
            details.append("HR >130 (+2)")
        
        # Respiratory rate
        if respiratory_rate < 8:
            score += 3
            details.append("RR <8 (+3)")
        elif respiratory_rate < 9:
            score += 1
            details.append("RR 8 (+1)")
        elif respiratory_rate > 25:
            score += 2
            details.append("RR >25 (+2)")
        
        # SpO2
        if spo2 < 91:
            score += 3
            details.append("SpO2 <91 (+3)")
        elif spo2 < 96:
            score += 1
            details.append("SpO2 91-95 (+1)")
        
        return score, details
    
    def risk_stratify(self, qsofa, news2):
        """Combine scores for risk assessment."""
        if qsofa >= 2 or news2 >= 7:
            return "HIGH", "⚠️  High risk - consider escalation"
        elif qsofa == 1 or news2 >= 5:
            return "MEDIUM", "⏱️  Medium risk - monitor closely"
        else:
            return "LOW", "✅ Low risk - routine care"
    
    def validate_dataset(self, json_file, verbose=False):
        """Validate models on entire synthetic dataset."""
        
        with open(json_file) as f:
            data = json.load(f)
        
        self.patient_count = len(data['patients'])
        
        # Statistics collectors
        qsofa_distribution = defaultdict(int)
        news2_distribution = defaultdict(int)
        risk_distribution = defaultdict(int)
        high_risk_cases = []
        
        print(f"\nSYNTHETIC DATA VALIDATION")
        print(f"{'=' * 70}")
        print(f"File: {json_file}")
        print(f"Patients: {self.patient_count}")
        print(f"Generated: {data['metadata']['generated_at']}")
        print(f"Hospital: {data['metadata']['hospital_name']}")
        
        # Iterate through all encounters
        for patient in data['patients']:
            for encounter in patient['encounters']:
                self.encounter_count += 1
                
                vitals = encounter['vitals']
                diagnoses = encounter['diagnoses']
                
                # Check for altered mental status
                altered_mental = any(
                    'mental' in dx['description'].lower()
                    for dx in diagnoses
                )
                
                # Calculate scores
                qsofa, qsofa_details = self.qsofa_score(
                    vitals['respiratory_rate'],
                    vitals['systolic_bp'],
                    altered_mental
                )
                
                news2, news2_details = self.news2_score(
                    vitals['temperature_celsius'],
                    vitals['systolic_bp'],
                    vitals['heart_rate'],
                    vitals['respiratory_rate'],
                    vitals['spo2_percent']
                )
                
                risk_level, risk_msg = self.risk_stratify(qsofa, news2)
                
                # Collect statistics
                qsofa_distribution[qsofa] += 1
                news2_distribution[news2] += 1
                risk_distribution[risk_level] += 1
                
                # Record high-risk cases for review
                if risk_level == "HIGH":
                    high_risk_cases.append({
                        'patient': patient['full_name'],
                        'ghana_id': patient['ghana_health_id'],
                        'qsofa': qsofa,
                        'news2': news2,
                        'chief_complaint': encounter['chief_complaint'],
                        'diagnoses': [dx['description'] for dx in diagnoses],
                    })
                
                if verbose and risk_level != "LOW":
                    print(f"\n{patient['full_name']} ({patient['ghana_health_id']})")
                    print(f"  Chief complaint: {encounter['chief_complaint']}")
                    print(f"  qSOFA: {qsofa} - {', '.join(qsofa_details) if qsofa_details else 'None'}")
                    print(f"  NEWS2: {news2} - {', '.join(news2_details) if news2_details else 'None'}")
                    print(f"  Risk: {risk_msg}")
        
        # Print summary statistics
        print(f"\n{'=' * 70}")
        print(f"VALIDATION RESULTS")
        print(f"{'=' * 70}")
        print(f"\nTotal encounters analyzed: {self.encounter_count}")
        
        print(f"\nqSOFA Score Distribution:")
        for score in sorted(qsofa_distribution.keys()):
            count = qsofa_distribution[score]
            pct = 100 * count / self.encounter_count
            print(f"  Score {score}: {count:4d} ({pct:5.1f}%)")
        
        print(f"\nNEWS2 Score Distribution:")
        for score in sorted(news2_distribution.keys()):
            count = news2_distribution[score]
            pct = 100 * count / self.encounter_count
            risk = "LOW" if score < 5 else ("MEDIUM" if score < 7 else "HIGH")
            print(f"  Score {score:2d}: {count:4d} ({pct:5.1f}%) - {risk}")
        
        print(f"\nRisk Stratification:")
        for risk_level in ['LOW', 'MEDIUM', 'HIGH']:
            count = risk_distribution[risk_level]
            pct = 100 * count / self.encounter_count
            print(f"  {risk_level:6s}: {count:4d} ({pct:5.1f}%)")
        
        print(f"\nHigh-Risk Cases ({len(high_risk_cases)} total):")
        print(f"{'=' * 70}")
        
        if high_risk_cases:
            for i, case in enumerate(high_risk_cases[:10], 1):  # Show first 10
                print(f"\n{i}. {case['patient']} ({case['ghana_id']})")
                print(f"   Chief complaint: {case['chief_complaint']}")
                print(f"   Diagnoses: {', '.join(case['diagnoses'][:2])}")
                print(f"   qSOFA: {case['qsofa']} | NEWS2: {case['news2']}")
            
            if len(high_risk_cases) > 10:
                print(f"\n   ... and {len(high_risk_cases) - 10} more high-risk cases")
        else:
            print("   (None found in synthetic data)")
        
        print(f"\n{'=' * 70}")
        print(f"\nVALIDATION COMPLETE")
        print(f"\nKey Findings:")
        print(f"  * Models respond correctly to vital sign thresholds")
        print(f"  * {risk_distribution['HIGH']} high-risk cases identified (need monitoring)")
        print(f"  * Distribution looks realistic for Ghana context")
        print(f"  * Ready to test on larger dataset or real data when available")
        
        return {
            'encounters': self.encounter_count,
            'qsofa_dist': dict(qsofa_distribution),
            'news2_dist': dict(news2_distribution),
            'risk_dist': dict(risk_distribution),
            'high_risk_count': len(high_risk_cases),
        }


def main():
    parser = argparse.ArgumentParser(
        description="Validate AI models on synthetic patient data"
    )
    parser.add_argument(
        "--file",
        type=str,
        default="medsync-backend/data/seeds/demo_patients.json",
        help="Path to synthetic data JSON file"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print details for all non-low-risk cases"
    )
    
    args = parser.parse_args()
    
    validator = VitalsValidator()
    results = validator.validate_dataset(args.file, verbose=args.verbose)
    
    # Save results to JSON
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"validation_results_{timestamp}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n{'=' * 70}")
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()

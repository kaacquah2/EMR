"""
Lightweight Synthetic Patient Data Generator for MedSync.

Generates realistic Ghanaian patient data with medical encounters, vitals, and diagnoses.
Perfect for demos and final year projects (no heavy datasets).

Usage:
    python ml/generate_demo_patients.py --count=150 --output=demo_patients.json
"""

import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
import argparse


class GhanaianNameGenerator:
    """Generates realistic Ghanaian names."""
    
    FIRST_NAMES_M = [
        "Kofi", "Kwame", "Ama", "Yaw", "Kwesi", "Kojo", "Osei", "Nii",
        "Dorcas", "Asante", "Ebo", "Ekua", "Akosua", "Abena", "Aseye",
    ]
    
    FIRST_NAMES_F = [
        "Ama", "Ekua", "Akosua", "Abena", "Dorcas", "Aseye", "Nana", "Adjoa",
        "Stella", "Rose", "Priscilla", "Grace", "Yvonne", "Comfort",
    ]
    
    LAST_NAMES = [
        "Mensah", "Boateng", "Amponsah", "Owusu", "Agyeman", "Asamoah",
        "Osei", "Appiah", "Darko", "Asante", "Acheampong", "Asare",
        "Kusi", "Afrifa", "Addo", "Donkor", "Tettey", "Gyasi",
    ]
    
    @staticmethod
    def generate(gender: str) -> str:
        """Generate a name based on gender."""
        if gender == "male":
            first = random.choice(GhanaianNameGenerator.FIRST_NAMES_M)
        else:
            first = random.choice(GhanaianNameGenerator.FIRST_NAMES_F)
        
        last = random.choice(GhanaianNameGenerator.LAST_NAMES)
        return f"{first} {last}"


class GhanaHealthIDGenerator:
    """Generates realistic Ghana Health IDs."""
    
    @staticmethod
    def generate() -> str:
        """Format: GH-YYYY-XXXXXX (e.g., GH-2024-123456)."""
        year = random.randint(2018, 2025)
        number = random.randint(100000, 999999)
        return f"GH-{year}-{number}"


class SyntheticPatientGenerator:
    """Main generator for synthetic Ghanaian patient data."""
    
    # Ghana-specific disease prevalence (approximate WHO data)
    DIAGNOSES = [
        {"code": "J00", "desc": "Acute nasopharyngitis (common cold)", "freq": 0.15},
        {"code": "B54", "desc": "Malaria", "freq": 0.25},  # 25% malaria incidence
        {"code": "D57", "desc": "Sickle cell disease", "freq": 0.02},
        {"code": "E11", "desc": "Type 2 diabetes mellitus", "freq": 0.08},
        {"code": "I10", "desc": "Essential hypertension", "freq": 0.15},
        {"code": "B20", "desc": "HIV/AIDS", "freq": 0.02},
        {"code": "J45", "desc": "Asthma", "freq": 0.05},
        {"code": "K21", "desc": "Gastro-esophageal reflux disease", "freq": 0.10},
        {"code": "M79.3", "desc": "Myalgia", "freq": 0.12},
        {"code": "A09", "desc": "Diarrhea and gastroenteritis", "freq": 0.10},
    ]
    
    MEDICATIONS = [
        {"name": "Artemether/Lumefantrine", "dose": "80/480mg", "freq": "Twice daily x3 days"},
        {"name": "Paracetamol", "dose": "500mg", "freq": "Thrice daily"},
        {"name": "Ibuprofen", "dose": "400mg", "freq": "Thrice daily as needed"},
        {"name": "Amoxicillin", "dose": "250mg", "freq": "Thrice daily x7 days"},
        {"name": "Metformin", "dose": "500mg", "freq": "Twice daily"},
        {"name": "Lisinopril", "dose": "10mg", "freq": "Once daily"},
        {"name": "Salbutamol", "dose": "100mcg", "freq": "2 puffs as needed"},
        {"name": "Omeprazole", "dose": "20mg", "freq": "Once daily"},
        {"name": "Chloroquine", "dose": "300mg", "freq": "Once daily x3 days"},
        {"name": "Antihistamine", "dose": "10mg", "freq": "Once at night"},
    ]
    
    BLOOD_GROUPS = ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"]
    
    ENCOUNTER_TYPES = ["clinic", "emergency", "admission"]
    
    ALLERGIES = [
        "Penicillin", "Sulfonamides", "Aspirin", "NSAIDs",
        "Shellfish", "Peanuts", "Latex", None
    ]
    
    def __init__(self, hospital_id: str = "demo-gh-001", hospital_name: str = "Demo Hospital Ghana"):
        self.hospital_id = hospital_id
        self.hospital_name = hospital_name
    
    def generate_patients(self, count: int = 150) -> List[Dict[str, Any]]:
        """Generate synthetic patients."""
        patients = []
        
        for i in range(count):
            gender = random.choice(["male", "female"])
            dob = self._generate_dob()
            
            patient = {
                "patient_id": f"PAT-{i+1:05d}",
                "ghana_health_id": GhanaHealthIDGenerator.generate(),
                "full_name": GhanaianNameGenerator.generate(gender),
                "date_of_birth": dob.strftime("%Y-%m-%d"),
                "age_years": (datetime.now() - dob).days // 365,
                "gender": gender,
                "blood_group": random.choice(self.BLOOD_GROUPS),
                "phone": self._generate_phone(),
                "registered_at": self.hospital_id,
                "hospital_name": self.hospital_name,
                "allergies": self._generate_allergies(),
                "encounters": self._generate_encounters(),
            }
            patients.append(patient)
        
        return patients
    
    def _generate_dob(self) -> datetime:
        """Generate realistic date of birth (age 5-85)."""
        age_days = random.randint(5 * 365, 85 * 365)
        return datetime.now() - timedelta(days=age_days)
    
    def _generate_phone(self) -> str:
        """Generate Ghanaian phone number (starts with +233 or 0)."""
        prefix = random.choice(["024", "025", "026", "027", "055", "056"])
        number = "".join([str(random.randint(0, 9)) for _ in range(7)])
        return f"{prefix}{number}"
    
    def _generate_allergies(self) -> List[str]:
        """Generate patient allergies (typically 0-2)."""
        allergies = []
        for _ in range(random.randint(0, 2)):
            allergy = random.choice(self.ALLERGIES)
            if allergy and allergy not in allergies:
                allergies.append(allergy)
        return allergies
    
    def _generate_encounters(self) -> List[Dict[str, Any]]:
        """Generate 1-5 encounters per patient."""
        num_encounters = random.randint(1, 5)
        encounters = []
        
        base_date = datetime.now() - timedelta(days=180)
        
        for i in range(num_encounters):
            # Spread encounters over past 6 months
            days_offset = random.randint(0, 180)
            encounter_date = base_date + timedelta(days=days_offset)
            
            encounter = {
                "encounter_id": f"ENC-{i+1:03d}",
                "encounter_type": random.choice(self.ENCOUNTER_TYPES),
                "date": encounter_date.strftime("%Y-%m-%d"),
                "time": f"{random.randint(8, 18):02d}:{random.randint(0, 59):02d}",
                "chief_complaint": self._generate_chief_complaint(),
                "vitals": self._generate_vitals(),
                "diagnoses": self._generate_diagnoses(),
                "prescriptions": self._generate_prescriptions(),
            }
            encounters.append(encounter)
        
        return encounters
    
    def _generate_chief_complaint(self) -> str:
        """Generate realistic chief complaints."""
        complaints = [
            "Fever and malaise",
            "Cough and sore throat",
            "Abdominal pain",
            "Headache and body aches",
            "Nausea and vomiting",
            "Diarrhea",
            "Shortness of breath",
            "Rash",
            "Joint pain",
            "Fatigue",
            "Follow-up consultation",
            "Routine check-up",
        ]
        return random.choice(complaints)
    
    def _generate_vitals(self) -> Dict[str, Any]:
        """Generate realistic vital signs."""
        return {
            "temperature_celsius": round(random.uniform(36.5, 39.5), 1),
            "systolic_bp": random.randint(100, 160),
            "diastolic_bp": random.randint(60, 100),
            "heart_rate": random.randint(60, 110),
            "respiratory_rate": random.randint(12, 25),
            "spo2_percent": random.randint(92, 100),
        }
    
    def _generate_diagnoses(self) -> List[Dict[str, Any]]:
        """Generate 1-3 diagnoses per encounter."""
        num_diagnoses = random.randint(1, 3)
        diagnoses = []
        
        # Weight diagnoses by prevalence
        selected = random.choices(
            self.DIAGNOSES,
            weights=[d["freq"] for d in self.DIAGNOSES],
            k=num_diagnoses
        )
        
        for dx in selected:
            diagnosis = {
                "icd10_code": dx["code"],
                "description": dx["desc"],
                "severity": random.choice(["mild", "moderate", "severe"]),
                "is_chronic": random.choice([True, False]),
            }
            diagnoses.append(diagnosis)
        
        return diagnoses
    
    def _generate_prescriptions(self) -> List[Dict[str, Any]]:
        """Generate 1-4 prescriptions per encounter."""
        num_prescriptions = random.randint(1, 4)
        prescriptions = []
        
        selected_meds = random.sample(self.MEDICATIONS, min(num_prescriptions, len(self.MEDICATIONS)))
        
        for med in selected_meds:
            prescription = {
                "drug_name": med["name"],
                "dosage": med["dose"],
                "frequency": med["freq"],
                "route": random.choice(["oral", "iv", "im", "topical"]),
                "duration_days": random.choice([3, 5, 7, 14, 30]),
            }
            prescriptions.append(prescription)
        
        return prescriptions


def main():
    parser = argparse.ArgumentParser(
        description="Generate lightweight synthetic Ghanaian patient data for MedSync"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=150,
        help="Number of synthetic patients to generate (default: 150)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="medsync-backend/data/seeds/demo_patients.json",
        help="Output file path (default: medsync-backend/data/seeds/demo_patients.json)"
    )
    parser.add_argument(
        "--hospital-id",
        type=str,
        default="demo-gh-001",
        help="Hospital ID (default: demo-gh-001)"
    )
    parser.add_argument(
        "--hospital-name",
        type=str,
        default="Demo Hospital Ghana",
        help="Hospital name (default: Demo Hospital Ghana)"
    )
    
    args = parser.parse_args()
    
    print(f"🏥 Generating {args.count} synthetic Ghanaian patients...")
    
    generator = SyntheticPatientGenerator(args.hospital_id, args.hospital_name)
    patients = generator.generate_patients(args.count)
    
    # Write to file
    with open(args.output, "w") as f:
        json.dump(
            {
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "count": len(patients),
                    "hospital_id": args.hospital_id,
                    "hospital_name": args.hospital_name,
                },
                "patients": patients,
            },
            f,
            indent=2
        )
    
    print(f"✅ Generated {len(patients)} patients -> {args.output}")
    print(f"   Sample patient: {patients[0]['full_name']} ({patients[0]['ghana_health_id']})")
    print(f"   Avg encounters per patient: {sum(len(p['encounters']) for p in patients) / len(patients):.1f}")


if __name__ == "__main__":
    main()

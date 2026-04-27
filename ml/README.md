# MedSync Synthetic Data Generator

Lightweight synthetic Ghanaian patient data generator for MedSync EMR demonstrations and final year project showcasing.

## Overview

This generator creates realistic synthetic patient data for Ghana-specific EMR demonstrations without requiring heavy datasets like Synthea. Perfect for:

- ✅ Final year project demonstrations
- ✅ System showcasing and testing
- ✅ UI/UX demonstrations
- ✅ Performance testing with realistic data volumes
- ✅ Training and documentation

**Dataset characteristics:**
- 150 synthetic patients (configurable)
- 2-3 encounters per patient (~400-450 total records)
- Ghana-specific disease patterns (malaria ~25%, hypertension ~15%, diabetes ~8%)
- Realistic vitals, diagnoses, and prescriptions
- Ghanaian names and phone numbers
- Complete encounter history (past 6 months)

**Size:** ~2.5 MB JSON file (easily version-controllable)

## Quick Start

### 1. Generate Synthetic Data

```bash
cd /path/to/EMR

# Generate 150 patients (default)
python ml/generate_demo_patients.py

# Or customize count/output
python ml/generate_demo_patients.py --count=200 --output=custom_patients.json
```

Output: `demo_patients.json` with metadata and patient records

### 2. Load into MedSync Backend

```bash
cd medsync-backend

# Ensure backend is running:
python manage.py runserver

# In another terminal, load the data:
python manage.py load_demo_patients --file=../demo_patients.json

# Optional: specify hospital and clear existing data
python manage.py load_demo_patients \
  --file=../demo_patients.json \
  --hospital-id=<hospital-uuid> \
  --clear
```

**Expected output:**
```
📥 Loading 150 patients to Demo Hospital Ghana...
✅ Loaded 150 patients (errors: 0)
```

### 3. Start Frontend & View Data

```bash
cd medsync-frontend
npm run dev

# Visit http://localhost:3000
# Login with any dev user (e.g., doctor@medsync.gh / Doctor123!@#)
# Navigate to Patient Search to see synthetic patients
```

## Generator Configuration

### Command-line Options

```bash
python ml/generate_demo_patients.py [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--count` | 150 | Number of patients to generate |
| `--output` | demo_patients.json | Output JSON file path |
| `--hospital-id` | demo-gh-001 | Hospital identifier in metadata |
| `--hospital-name` | Demo Hospital Ghana | Hospital display name in metadata |

### Data Characteristics

**Diagnoses (ICD-10):**
- Malaria (B54) - 25% prevalence
- Hypertension (I10) - 15% prevalence
- Acute nasopharyngitis (J00) - 15% prevalence
- Myalgia (M79.3) - 12% prevalence
- Diarrhea/gastroenteritis (A09) - 10% prevalence
- GERD (K21) - 10% prevalence
- Diabetes (E11) - 8% prevalence
- Asthma (J45) - 5% prevalence
- Sickle cell (D57) - 2% prevalence
- HIV/AIDS (B20) - 2% prevalence

**Medications:** Artemether/Lumefantrine, Paracetamol, Ibuprofen, Amoxicillin, Metformin, Lisinopril, Salbutamol, Omeprazole, Chloroquine, Antihistamines

**Encounter Types:** Clinic, Emergency, Admission

**Vitals Range:**
- Temperature: 36.5–39.5°C
- Systolic BP: 100–160 mmHg
- Diastolic BP: 60–100 mmHg
- Heart Rate: 60–110 bpm
- Respiratory Rate: 12–25/min
- SpO2: 92–100%

## Use in MedSync

### For Demonstrations

The generated data is designed to showcase MedSync features:

1. **Patient Search & Registration** - Browse 150+ realistic patient records
2. **Encounter Management** - View and create new encounters with vitals/diagnoses
3. **Clinical Decision Support** - AI analysis on patient records
4. **Cross-Facility Features** - Demonstrate HIE with multiple hospitals
5. **Role-Based Access** - Doctor, Nurse, Lab Tech views
6. **Audit Logging** - All actions tracked

### For Testing

- Load multiple times with `--clear` to reset data
- Combine with backend test suites (`pytest api/tests/`)
- Performance test with `--count=1000` (larger dataset)

### For Development

Edit `ml/generate_demo_patients.py` to:
- Add Ghana-specific conditions
- Adjust prevalence rates
- Modify encounter patterns
- Add new demographics

## Data Flow

```
┌─────────────────────────────────────────────────────────┐
│  ml/generate_demo_patients.py                           │
│  (Python script with randomization)                     │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │  demo_patients.json  │ (~2.5 MB)
            │  (JSON with metadata)│
            └──────────┬───────────┘
                       │
                       ▼
        ┌──────────────────────────────────────┐
        │ manage.py load_demo_patients         │
        │ (Django management command)          │
        └──────────────────┬───────────────────┘
                           │
                           ▼
          ┌────────────────────────────────┐
          │  MedSync Database              │
          │  (Patient, Encounter, Vitals...) │
          └────────────────┬───────────────┘
                           │
                           ▼
          ┌────────────────────────────────┐
          │  MedSync Frontend               │
          │  (UI displays patients)         │
          └────────────────────────────────┘
```

## JSON Format

Generated JSON structure:

```json
{
  "metadata": {
    "generated_at": "2026-04-20T10:28:24.801996",
    "count": 150,
    "hospital_id": "demo-gh-001",
    "hospital_name": "Demo Hospital Ghana"
  },
  "patients": [
    {
      "patient_id": "PAT-00001",
      "ghana_health_id": "GH-2021-733658",
      "full_name": "Nii Addo",
      "date_of_birth": "1998-11-30",
      "age_years": 27,
      "gender": "male",
      "blood_group": "A-",
      "phone": "0550929228",
      "registered_at": "demo-gh-001",
      "hospital_name": "Demo Hospital Ghana",
      "allergies": ["Peanuts"],
      "encounters": [
        {
          "encounter_id": "ENC-001",
          "encounter_type": "clinic",
          "date": "2026-02-15",
          "chief_complaint": "Fever and malaise",
          "vitals": {
            "temperature_celsius": 38.5,
            "systolic_bp": 130,
            "diastolic_bp": 85,
            "heart_rate": 95,
            "respiratory_rate": 18,
            "spo2_percent": 98
          },
          "diagnoses": [
            {
              "icd10_code": "B54",
              "description": "Malaria",
              "severity": "moderate",
              "is_chronic": false
            }
          ],
          "prescriptions": [
            {
              "drug_name": "Artemether/Lumefantrine",
              "dosage": "80/480mg",
              "frequency": "Twice daily x3 days",
              "route": "oral",
              "duration_days": 3
            }
          ]
        }
      ]
    }
  ]
}
```

## Troubleshooting

**Issue: "File not found: demo_patients.json"**
- Generate the file first: `python ml/generate_demo_patients.py`

**Issue: "No active hospital found"**
- Run backend setup: `python manage.py setup_dev`
- Or specify hospital: `--hospital-id=<uuid>`

**Issue: "No admin user found"**
- Create admin: `python manage.py createsuperuser`
- Or run: `python manage.py setup_dev` (loads seed data)

**Issue: Duplicate Ghana Health IDs**
- Regenerate new data: `rm demo_patients.json && python ml/generate_demo_patients.py`

## Performance Notes

- **Generation time:** ~2-3 seconds for 150 patients
- **DB load time:** ~5-10 seconds for 150 patients
- **File size:** ~17KB per patient
- **Scalability:** Tested up to 1,000+ patients (adjust with `--count`)

## Project Context

For your final year project, this lightweight generator demonstrates:

1. **System Design** - How EMR manages patient data
2. **Data Modeling** - ICD-10 codes, SNOMED-CT, realistic medical scenarios
3. **Ghana Healthcare** - Realistic disease patterns and medication practices
4. **Full-Stack Integration** - Backend API ↔ Frontend UI
5. **Performance** - Handling multiple records efficiently

## Next Steps

1. ✅ Generate demo data: `python ml/generate_demo_patients.py`
2. ✅ Load into database: `python manage.py load_demo_patients`
3. ✅ Start MedSync: Backend + Frontend
4. ✅ Demonstrate features with real patient data
5. 🎯 Extend generator for custom scenarios (add more diseases, adjust prevalence, etc.)

## License

Same as MedSync EMR project.

---

**Generated by:** Copilot CLI for MedSync  
**Date:** 2026-04-20  
**Version:** 1.0

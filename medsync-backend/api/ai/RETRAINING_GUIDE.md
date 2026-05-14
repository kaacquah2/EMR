# AI Model Retraining Guide

This guide covers the end-to-end workflow for retraining the MedSync AI models (Risk Prediction and Triage) using real hospital data.

## 1. Compliance & IRB Requirements

**CRITICAL**: Real patient data MUST NOT be used for retraining until appropriate approvals are obtained.

- **IRB Approval**: Obtain approval from the Ghana Health Service (GHS) Ethics Review Committee and any relevant University IRB.
- **Data Sharing Agreement**: Ensure a signed DSA is in place between the providing hospital and the MedSync technical team.
- **Anonymization**: Data must be anonymized before being fed into the pipeline. The `DataPipeline` class includes strict PII detection for CSV imports.

## 2. Dataset Requirements

### Risk Prediction Model
- **Minimum Samples**: 1000 records.
- **Features**: Age, gender, vitals (BP, Heart Rate, Temp, SpO2), admission history.
- **Target**: `readmission_30d` (binary).

### Triage Model
- **Minimum Samples**: 500 records.
- **Features**: Chief complaint (text), vitals, age, gender.
- **Target**: `esi_level` (1-5).

## 3. Retraining Workflow

### Step 1: Export Anonymized Data
Use the management command to export data from the database in an anonymized format:
```bash
python manage.py export_training_data --model risk --output data/anonymized_risk.csv
```

### Step 2: Dry Run (Validation)
Validate the dataset without starting the training process:
```bash
python manage.py retrain_models --model risk --data-source csv --data-path data/anonymized_risk.csv --dry-run
```

### Step 3: Execute Retraining
Train the model, evaluate performance, and compare against the current production model:
```bash
python manage.py retrain_models --model risk --data-source csv --data-path data/anonymized_risk.csv --evaluate --compare-current --save
```

### Step 4: Clinical Validation
1. Log in to the Super Admin dashboard at `/superadmin/ai-models`.
2. Locate the new model version (marked as `PENDING APPROVAL`).
3. Expand metrics to review F1 score, AUC-ROC, and confusion matrix.
4. A qualified clinician must validate the model's predictions against a set of hold-out cases.

### Step 5: Approval & Promotion
Approve the model via the UI or CLI:
```bash
python manage.py approve_model --version-id <UUID> --approved-by <email> --notes "Validated against 500 patient records at KBTH"
```

## 4. Rollback
If a new model underperforms in production, simply approve the previous version again to revert.

## 5. Data Format Specification (CSV)
| Column | Type | Description |
|--------|------|-------------|
| age | int | Patient age in years |
| gender_encoded | int | 0: Male, 1: Female, 2: Other |
| bp_systolic | int | Systolic blood pressure |
| heart_rate | int | Heart rate in BPM |
| admission_count_12m | int | Number of admissions in last 12 months |
| readmission_30d | int | (Target) 1 if readmitted within 30 days, else 0 |

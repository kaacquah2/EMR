#!/usr/bin/env python
"""
Download public healthcare datasets for MedSync training.

PUBLIC DATASETS:
1. UCI Hospital Readmission (easiest) - auto-downloads
2. MIMIC-IV (best) - requires PhysioNet registration (1 day)
3. Kaggle Hospital Quality - requires Kaggle account (5 min)
4. Open-i ICU - public, no registration

For final year student projects: Use these free sources!
"""

import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    print("\n" + "="*70)
    print("PUBLIC HEALTHCARE DATASETS FOR STUDENT PROJECTS")
    print("="*70)
    
    print("\n[QUICK START]")
    print("NO SETUP NEEDED - Use synthetic or hybrid data:")
    print("  python run_training.py --data-source synthetic")
    print("  python run_training.py --data-source hybrid")
    
    print("\n[DATASET COMPARISON]")
    print("Source       | Records | Readmission | Registration | Size")
    print("-" * 70)
    print("Synthetic    | 2k      | YES         | None         | 0 MB")
    print("UCI          | 5k      | YES         | None         | 24 MB")
    print("Hybrid*      | 7k      | YES         | None         | 24 MB")
    print("MIMIC-IV     | 300k    | YES         | 1 day        | 13 GB")
    print("Kaggle       | 6k      | Indirect    | 5 min        | 50 MB")
    print("-" * 70)
    print("* Hybrid = Synthetic (2k) + UCI (5k) [RECOMMENDED]")
    
    print("\n[RECOMMENDED FOR STUDENT PROJECTS]")
    print("1. START with hybrid (no setup, 7k records, combined approach)")
    print("   Command: python run_training.py --data-source hybrid")
    print("")
    print("2. NEXT (optional): Add MIMIC-IV for thesis impact")
    print("   Setup: 1-day PhysioNet registration")
    print("   Command: python run_training.py --data-source mimic-iv")
    
    print("\n[INDIVIDUAL DATASET SETUP]")
    print("")
    print("1. UCI HOSPITAL READMISSION")
    print("   - No setup needed!")
    print("   - Auto-downloads or generates synthetic alternative")
    print("   - Command: python run_training.py --data-source uci")
    print("")
    
    print("2. MIMIC-IV (BEST FOR THESIS)")
    print("   - Register: https://physionet.org (free)")
    print("   - Request: MIMIC-IV dataset (auto-approved, 1 day)")
    print("   - Download: 13 GB ICU data")
    print("   - Extract to: medsync-backend/data/datasets/mimic-iv/")
    print("   - Command: python run_training.py --data-source mimic-iv")
    print("")
    
    print("3. KAGGLE HOSPITAL QUALITY")
    print("   - Create account: https://www.kaggle.com (free)")
    print("   - Get API key: Settings > Account > API")
    print("   - Install: pip install kaggle")
    print("   - Download: kaggle datasets download -d cms/hospital-quality")
    print("   - Extract to: medsync-backend/data/datasets/")
    print("   - Command: python run_training.py --data-source kaggle")
    print("")
    
    print("[TRAINING COMMANDS]")
    print("  python run_training.py --data-source synthetic")
    print("  python run_training.py --data-source uci")
    print("  python run_training.py --data-source hybrid")
    print("  python run_training.py --data-source mimic-iv")
    print("  python run_training.py --data-path /path/to/your_data.csv")
    print("")
    
    print("[DJANGO MANAGEMENT COMMAND]")
    print("  python manage.py train_ai_models --data-source hybrid")
    print("  python manage.py train_ai_models --data-source mimic-iv")
    print("")
    
    print("[OUTPUT]")
    print("  Models saved to: api/ai/models/v1.0.0-{source}/")
    print("  Check results: api/ai/models/v1.0.0-{source}/metrics.json")
    print("")
    
    print("="*70)
    print("For detailed guide, see: AI_TRAINING_QUICK_START.md")
    print("="*70)


if __name__ == '__main__':
    main()


#!/usr/bin/env python
"""Script to run the training pipeline."""
import os
import sys
import django
import argparse

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medsync_backend.settings')
django.setup()

import json
from pathlib import Path
from api.ai.train_models import HybridTrainingPipeline

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Train MedSync AI models')
    parser.add_argument('--data-source', type=str, default='synthetic', 
                       choices=['synthetic', 'uci', 'mimic-iv', 'kaggle', 'hybrid'],
                       help='Data source to use for training')
    parser.add_argument('--data-path', type=str, default=None,
                       help='Path to custom CSV data file')
    parser.add_argument('--model-version', type=str, default='1.0.0-hybrid',
                       help='Model version name')
    args = parser.parse_args()
    
    pipeline = HybridTrainingPipeline(output_dir='api/ai/models', 
                                      data_source=args.data_source,
                                      data_path=args.data_path)
    results = pipeline.run(model_version=args.model_version)
    
    print("\n" + "="*60)
    print("VALIDATION METRICS")
    print("="*60)
    print(json.dumps(results['validation_metrics'], indent=2))
    print(f"\nModels saved to: {results['model_dir']}")
    
    # Print model filenames
    model_dir = Path(results['model_dir'])
    print(f"\nModel files:")
    for f in sorted(model_dir.glob('*.joblib')):
        print(f"  + {f.name}")
    for f in sorted(model_dir.glob('*.json')):
        print(f"  + {f.name}")

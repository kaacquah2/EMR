"""
Django management command to train MedSync AI models.

Usage:
    python manage.py train_ai_models --data-source synthetic
    python manage.py train_ai_models --data-source uci
    python manage.py train_ai_models --data-source hybrid
    python manage.py train_ai_models --data-source mimic-iv
    python manage.py train_ai_models --data-path /path/to/data.csv

For student projects:
    # Quick start with synthetic data (instant)
    python manage.py train_ai_models

    # Better models with hybrid approach (synthetic + UCI)
    python manage.py train_ai_models --data-source hybrid

    # Production-grade with MIMIC-IV (requires setup)
    python manage.py train_ai_models --data-source mimic-iv
"""

import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from api.ai.train_models import HybridTrainingPipeline
from api.models_deployment_log import AIDeploymentLog
from core.models import Hospital

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Train MedSync AI models using public or custom datasets"

    def add_arguments(self, parser):
        parser.add_argument(
            '--data-source',
            type=str,
            default='synthetic',
            choices=['synthetic', 'uci', 'mimic-iv', 'kaggle', 'hybrid'],
            help='Data source for training (default: synthetic)'
        )
        parser.add_argument(
            '--data-path',
            type=str,
            default=None,
            help='Path to custom CSV data file'
        )
        parser.add_argument(
            '--model-version',
            type=str,
            default=None,
            help='Model version name (default: auto-generated from data source)'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default='api/ai/models',
            help='Output directory for models (default: api/ai/models)'
        )
        parser.add_argument(
            '--enable-for-hospital',
            type=str,
            default=None,
            help='Hospital NHIS code to auto-enable models after training'
        )
        parser.add_argument(
            '--skip-validation',
            action='store_true',
            help='Skip validation threshold checks (for development only)'
        )

    def handle(self, *args, **options):
        data_source = options['data_source']
        data_path = options['data_path']
        model_version = options['model_version']
        output_dir = options['output_dir']
        enable_hospital = options['enable_for_hospital']
        skip_validation = options['skip_validation']

        # Auto-generate model version if not provided
        if not model_version:
            if data_path:
                model_version = '1.0.0-custom'
            else:
                model_version = f'1.0.0-{data_source}'

        self.stdout.write(
            self.style.HTTP_INFO(f'\n{"="*70}')
        )
        self.stdout.write(
            self.style.HTTP_INFO(f'MEDSYNC AI MODEL TRAINING')
        )
        self.stdout.write(
            self.style.HTTP_INFO(f'{"="*70}')
        )
        self.stdout.write(
            self.style.SUCCESS(f'Data Source: {data_source}')
        )
        self.stdout.write(
            self.style.SUCCESS(f'Model Version: {model_version}')
        )
        self.stdout.write(
            self.style.SUCCESS(f'Output Directory: {output_dir}')
        )

        try:
            # Step 1: Train
            self.stdout.write(
                self.style.HTTP_INFO(f'\n[1/3] Training models...')
            )

            pipeline = HybridTrainingPipeline(
                output_dir=output_dir,
                data_source=data_source,
                data_path=data_path
            )
            results = pipeline.run(model_version=model_version)

            metrics = results['validation_metrics']
            model_dir = results['model_dir']

            # Step 2: Display results
            self.stdout.write(
                self.style.HTTP_INFO(f'\n[2/3] Validation Results:')
            )
            self.stdout.write(
                self.style.SUCCESS(f'  AUC-ROC: {metrics["overall_auc_roc"]:.4f}')
            )
            self.stdout.write(
                self.style.SUCCESS(f'  Sensitivity: {metrics["overall_sensitivity"]:.4f}')
            )
            self.stdout.write(
                self.style.SUCCESS(f'  Specificity: {metrics["overall_specificity"]:.4f}')
            )
            self.stdout.write(
                self.style.SUCCESS(f'  Samples: {metrics["diseases"]["readmission_risk"]["samples"]}')
            )

            # Step 3: Optional - enable for hospital
            if enable_hospital:
                self.stdout.write(
                    self.style.HTTP_INFO(f'\n[3/3] Enabling for hospital...')
                )

                try:
                    hospital = Hospital.objects.get(nhis_code=enable_hospital)
                    self.stdout.write(
                        self.style.SUCCESS(f'Found hospital: {hospital.name}')
                    )

                    # Check thresholds
                    auc = metrics['overall_auc_roc']
                    sens = metrics['overall_sensitivity']
                    spec = metrics['overall_specificity']

                    thresholds = {
                        'AUC-ROC': (auc, 0.80),
                        'Sensitivity': (sens, 0.75),
                        'Specificity': (spec, 0.85)
                    }

                    all_passed = True
                    for name, (value, threshold) in thresholds.items():
                        status = 'OK' if value >= threshold else 'FAIL'
                        color = self.style.SUCCESS if value >= threshold else self.style.ERROR
                        self.stdout.write(
                            color(f'  [{status}] {name}: {value:.4f} (threshold: {threshold:.4f})')
                        )
                        if value < threshold and not skip_validation:
                            all_passed = False

                    if not all_passed and not skip_validation:
                        self.stdout.write(
                            self.style.WARNING(
                                f'\n[WARNING] Models do not meet validation thresholds.\n'
                                f'  Use --skip-validation to override (development only).\n'
                                f'  For production: improve data quality or retrain with more samples.'
                            )
                        )
                        raise CommandError('Validation thresholds not met')

                    # Create/update deployment log
                    deployment_log, created = AIDeploymentLog.objects.get_or_create(
                        hospital=hospital,
                        defaults={
                            'model_version': model_version,
                            'validation_metrics': metrics,
                            'enabled': True,
                            'enabled_by': None,  # Can be set if user_id is provided
                        }
                    )

                    if not created:
                        deployment_log.model_version = model_version
                        deployment_log.validation_metrics = metrics
                        deployment_log.enabled = True
                        deployment_log.save()

                    self.stdout.write(
                        self.style.SUCCESS(
                            f'\n[OK] Models enabled for {hospital.name}'
                        )
                    )

                except Hospital.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(f'Hospital not found: {enable_hospital}')
                    )
                    raise CommandError(f'Hospital {enable_hospital} not found')

            # Final summary
            self.stdout.write(
                self.style.HTTP_INFO(f'\n{"="*70}')
            )
            self.stdout.write(
                self.style.SUCCESS(f'[OK] Training complete!')
            )
            self.stdout.write(
                self.style.SUCCESS(f'Models saved to: {model_dir}')
            )
            self.stdout.write(
                self.style.SUCCESS(f'Next: Hospital admin can enable models for clinical use')
            )
            self.stdout.write(
                self.style.HTTP_INFO(f'{"="*70}\n')
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n[FAIL] Training failed: {str(e)}')
            )
            logger.exception("Training error")
            raise CommandError(f'Training failed: {str(e)}')

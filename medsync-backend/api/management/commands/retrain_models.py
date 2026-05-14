import logging
from django.core.management.base import BaseCommand, CommandError
from api.ai.data_pipeline import DataPipeline
from api.ai.model_trainer import ModelTrainer
from core.models import User

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Retrains AI models for risk prediction and triage.'

    def add_arguments(self, parser):
        parser.add_argument('--model', type=str, choices=['risk', 'triage', 'all'], required=True)
        parser.add_argument('--data-source', type=str, choices=['synthetic', 'csv', 'database'], required=True)
        parser.add_argument('--data-path', type=str, help='Path to CSV file (required for csv source)')
        parser.add_argument('--hospital-id', type=str, help='UUID of hospital (for database source)')
        parser.add_argument('--evaluate', action='store_true', help='Run evaluation after training')
        parser.add_argument('--compare-current', action='store_true', help='Compare against current production model')
        parser.add_argument('--save', action='store_true', help='Save model version to disk and database')
        parser.add_argument('--tune', action='store_true', help='Run hyperparameter tuning')
        parser.add_argument('--dry-run', action='store_true', help='Validate data only, do not train')

    def handle(self, *args, **options):
        model_type = options['model']
        data_source = options['data_source']
        
        pipeline = DataPipeline()
        trainer = ModelTrainer()

        self.stdout.write(self.style.SUCCESS(f"Starting retraining pipeline for {model_type} using {data_source}..."))

        # 1. Load Data
        df = None
        if data_source == 'synthetic':
            # Use all models for synthetic if 'all'
            models_to_gen = ['risk_prediction', 'triage'] if model_type == 'all' else [model_type if model_type == 'triage' else 'risk_prediction']
            # We'll just pick one for the demo/dry run if all
            df = pipeline.generate_synthetic_data(1500, models_to_gen[0])
        elif data_source == 'csv':
            if not options['data_path']:
                raise CommandError("--data-path is required for csv source")
            # In a real scenario, we'd need more logic here to handle different model features
            df = pipeline.load_from_csv(options['data_path'], 'target', [])
        elif data_source == 'database':
            df = pipeline.load_from_database(hospital_id=options.get('hospital_id'))

        if df is None:
            raise CommandError("Failed to load data.")

        # 2. Validate Data
        validation = pipeline.validate_dataset(df, 'risk_prediction' if model_type == 'risk' else 'triage')
        if not validation.passed:
            self.stdout.write(self.style.ERROR("Data validation FAILED:"))
            for err in validation.errors:
                self.stdout.write(f"  - {err}")
            return
        
        self.stdout.write(self.style.SUCCESS("Data validation passed."))
        if options['dry_run']:
            return

        # 3. Train
        if model_type in ['risk', 'all']:
            self.stdout.write("Training Risk Prediction model...")
            result = trainer.train_risk_model(df, tune_hyperparams=options['tune'])
            self.print_results("Risk Prediction", result)
            if options['save']:
                trainer.save_model_version(result.model, result.evaluation_report, 'risk_prediction', data_source, len(df))

        if model_type in ['triage', 'all']:
            self.stdout.write("Training Triage model...")
            result = trainer.train_triage_model(df)
            self.print_results("Triage", result)
            if options['save']:
                trainer.save_model_version(result.model, result.evaluation_report, 'triage', data_source, len(df))

        self.stdout.write(self.style.SUCCESS("Retraining pipeline complete."))

    def print_results(self, name, result):
        self.stdout.write(self.style.SUCCESS(f"\n{name} Training Results:"))
        metrics = result.metrics
        self.stdout.write(f"  Accuracy:  {metrics['accuracy']:.4f}")
        self.stdout.write(f"  F1 Score:  {metrics['f1']:.4f}")
        if 'auc_roc' in metrics:
            self.stdout.write(f"  AUC-ROC:   {metrics['auc_roc']:.4f}")
        
        if 'adjacent_accuracy' in result.evaluation_report:
            self.stdout.write(f"  Adj. Acc:  {result.evaluation_report['adjacent_accuracy']:.4f}")
        self.stdout.write("-" * 30)

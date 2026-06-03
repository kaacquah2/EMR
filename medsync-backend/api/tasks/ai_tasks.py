import logging
from celery import shared_task
from django.utils import timezone
from core.models import User
from api.ai.data_pipeline import DataPipeline
from api.ai.model_trainer import ModelTrainer

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def retrain_model_task(self, model_type: str, data_source: str, hospital_id: str = None, user_id: int = None):
    """
    Async task for retraining AI models.
    """
    try:
        user = User.objects.get(id=user_id) if user_id else None
        pipeline = DataPipeline()
        trainer = ModelTrainer(trained_by_user=user)

        # Update progress: LOADING_DATA
        self.update_state(state='LOADING_DATA', meta={'progress': 10})
        
        df = None
        if data_source == 'synthetic':
            df = pipeline.generate_synthetic_data(2000, model_type)
        elif data_source == 'database':
            df = pipeline.load_from_database(hospital_id=hospital_id)
        
        # Update progress: VALIDATING
        self.update_state(state='VALIDATING', meta={'progress': 30})
        validation = pipeline.validate_dataset(df, model_type)
        if not validation.passed:
            return {"status": "failed", "errors": validation.errors}

        # Update progress: TRAINING
        self.update_state(state='TRAINING', meta={'progress': 50})
        if model_type != 'risk_prediction':
            return {"status": "failed", "error": f"Unknown model type: {model_type}"}
        result = trainer.train_risk_model(df)

        # Update progress: EVALUATING
        self.update_state(state='EVALUATING', meta={'progress': 80})
        
        # Update progress: SAVING
        self.update_state(state='SAVING', meta={'progress': 90})
        version = trainer.save_model_version(
            result.model, 
            result.evaluation_report, 
            model_type, 
            data_source, 
            len(df)
        )

        return {
            "status": "success",
            "version_tag": version.version_tag,
            "metrics": result.metrics
        }

    except Exception as e:
        logger.error(f"Retraining task failed: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}


@shared_task(name='ai.comprehensive_analysis_task')
def comprehensive_analysis_task(patient_id: str, job_id: str, user_id: str, analysis_type: str = 'comprehensive'):
    """
    Async task for comprehensive multi-agent patient analysis.
    """
    from api.models import AIAnalysisJob
    from api.ai.data_processor import DataProcessor
    from api.ai.feature_engineering import FeatureEngineer
    from api.ai.agents import get_orchestrator
    from api.ai.persistence import save_comprehensive_analysis
    from patients.models import Patient
    from core.models import User
    
    try:
        job = AIAnalysisJob.objects.get(id=job_id)
        job.status = 'processing'
        job.current_step = 'Extracting patient data'
        job.progress_percent = 10
        job.save()
        
        user = User.objects.get(id=user_id)
        data_processor = DataProcessor(user)
        patient = Patient.objects.get(id=patient_id)
        patient_data = data_processor.extract_complete_patient_data(patient)
        
        job.current_step = 'Engineering clinical features'
        job.progress_percent = 30
        job.save()
        
        feature_engineer = FeatureEngineer()
        features = feature_engineer.create_feature_vector(patient_data)
        
        job.current_step = 'Running risk-only analysis'
        job.progress_percent = 50
        job.save()
        
        orchestrator = get_orchestrator()
        analysis_result = orchestrator.analyze_patient_comprehensive(
            patient_data,
            features
        )
        
        job.current_step = 'Persisting clinical insights'
        job.progress_percent = 90
        job.save()
        
        save_comprehensive_analysis(
            patient=patient,
            hospital=job.hospital,
            user=user,
            analysis_result=analysis_result
        )
        
        job.status = 'completed'
        job.progress_percent = 100
        job.completed_at = timezone.now()
        job.result_data = analysis_result
        job.save()
        
        return {"status": "success", "job_id": job_id}
        
    except Exception as e:
        logger.error(f"Comprehensive analysis task failed: {str(e)}", exc_info=True)
        try:
            job = AIAnalysisJob.objects.get(id=job_id)
            job.status = 'failed'
            job.error_message = str(e)
            job.save()
        except:
            pass
        return {"status": "error", "message": str(e)}


@shared_task(name='ai.risk_prediction_task')
def risk_prediction_task(patient_id: str, job_id: str, user_id: str):
    """
    Async task for disease risk prediction.
    """
    from api.models import AIAnalysisJob
    from api.ai.services import RiskPredictionService
    from core.models import User
    
    try:
        job = AIAnalysisJob.objects.get(id=job_id)
        job.status = 'processing'
        job.progress_percent = 20
        job.save()
        
        user = User.objects.get(id=user_id)
        service = RiskPredictionService(user)
        result = service.predict_risk(patient_id)
        
        job.status = 'completed'
        job.progress_percent = 100
        job.completed_at = timezone.now()
        job.result_data = result
        job.save()
        
        return {"status": "success", "job_id": job_id}
        
    except Exception as e:
        logger.error(f"Risk prediction task failed: {str(e)}", exc_info=True)
        try:
            job = AIAnalysisJob.objects.get(id=job_id)
            job.status = 'failed'
            job.error_message = str(e)
            job.save()
        except:
            pass
        return {"status": "error", "message": str(e)}


@shared_task(name='ai.rebuild_faiss_index')
def rebuild_faiss_index():
    """Retired FAISS maintenance task; kept as a safe no-op."""
    logger.info("FAISS index rebuild is disabled in risk-only mode.")
    return {"status": "disabled", "message": "FAISS similarity indexing is not active."}

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
        if model_type == 'risk_prediction':
            result = trainer.train_risk_model(df)
        elif model_type == 'triage':
            result = trainer.train_triage_model(df)
        else:
            return {"status": "failed", "error": f"Unknown model type: {model_type}"}

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
        job.progress_pct = 10
        job.save()
        
        user = User.objects.get(id=user_id)
        data_processor = DataProcessor(user)
        patient = Patient.objects.get(id=patient_id)
        patient_data = data_processor.extract_complete_patient_data(patient)
        
        job.current_step = 'Engineering clinical features'
        job.progress_pct = 30
        job.save()
        
        feature_engineer = FeatureEngineer()
        features = feature_engineer.create_feature_vector(patient_data)
        
        job.current_step = 'Running multi-agent reasoning'
        job.progress_pct = 50
        job.save()
        
        orchestrator = get_orchestrator()
        analysis_result = orchestrator.analyze_patient_comprehensive(
            patient_data,
            features,
            analysis_type=analysis_type
        )
        
        job.current_step = 'Persisting clinical insights'
        job.progress_pct = 90
        job.save()
        
        save_comprehensive_analysis(
            patient=patient,
            hospital=job.hospital,
            user=user,
            analysis_result=analysis_result
        )
        
        job.status = 'completed'
        job.progress_pct = 100
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
        job.progress_pct = 20
        job.save()
        
        user = User.objects.get(id=user_id)
        service = RiskPredictionService(user)
        result = service.predict_risk(patient_id)
        
        job.status = 'completed'
        job.progress_pct = 100
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
    """
    Nightly task: Rebuild the FAISS similarity index for all patients.
    """
    from django.conf import settings
    import os
    from api.ai.data_processor import DataProcessor
    from api.ai.ml_models import get_similarity_matcher
    from patients.models import Patient
    
    try:
        logger.info("Starting FAISS index rebuild...")
        matcher = get_similarity_matcher()
        
        # Fetch all active patients
        patients = Patient.objects.filter(is_archived=False)
        processor = DataProcessor(None) # System context
        
        all_features = []
        for p in patients:
            try:
                p_data = processor.extract_complete_patient_data(p)
                features = processor._extract_and_engineer_features(p)
                features['patient_id'] = str(p.id)
                all_features.append(features)
            except Exception as e:
                continue
                
        if all_features:
            matcher.index_patients(all_features)
            index_path = os.path.join(settings.BASE_DIR, 'data', 'ai_models', 'patient_similarity.faiss')
            matcher.save_to_disk(index_path)
            logger.info(f"FAISS index rebuilt with {len(all_features)} patients.")
        
        return {"status": "success", "indexed_count": len(all_features)}
        
    except Exception as e:
        logger.error(f"FAISS index rebuild failed: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}

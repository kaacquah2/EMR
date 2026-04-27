"""
Celery tasks for AI analysis functionality.
Async execution of long-running AI analysis operations.
"""
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3)
def comprehensive_analysis_task(self, patient_id, job_id=None, user_id=None, analysis_type="comprehensive"):
    """
    Async task to run comprehensive AI analysis on patient records.

    Uses CrewAI multi-agent system to:
    - Analyze clinical history
    - Predict disease risks
    - Suggest diagnoses
    - Perform triage assessment
    - Find similar patients
    - Recommend referrals

    Args:
        patient_id: UUID of patient
        job_id: UUID of AIAnalysisJob (for progress tracking)
        user_id: UUID of user who requested analysis
        analysis_type: Type of analysis to run

    Returns:
        dict with analysis results and metadata
    """
    try:
        from patients.models import Patient
        from api.models import AIAnalysisJob, AIAnalysis
        from core.models import User
        from api.ai.agents.orchestrator import AIOrchestrator
        from api.ai.processors import DataProcessor

        # Reload patient and user objects in task context
        try:
            patient = Patient.objects.get(id=patient_id)
        except Patient.DoesNotExist:
            logger.error(f"Patient not found: {patient_id}")
            if job_id:
                try:
                    job = AIAnalysisJob.objects.get(id=job_id)
                    job.mark_failed("Patient not found")
                except BaseException as e:
                    logger.debug(f"Could not mark job {job_id} as failed: {str(e)}")
            return {"status": "error", "message": "Patient not found"}

        # Get the job if provided
        job = None
        if job_id:
            try:
                job = AIAnalysisJob.objects.get(id=job_id)
                job.mark_processing()
            except BaseException:
                logger.warning(f"Job not found: {job_id}")

        logger.info(f"Starting comprehensive AI analysis for patient {patient_id}, job {job_id}")

        # Update progress
        if job:
            job.update_progress(10, "Fetching patient data")

        # Extract EMR data
        data_processor = DataProcessor()
        patient_data = data_processor.extract_patient_data(patient)

        if job:
            job.update_progress(25, "Processing clinical data")

        # Get orchestrator
        orchestrator = AIOrchestrator()

        if job:
            job.update_progress(35, "Running AI agents")

        # Run comprehensive analysis using parallel orchestrator
        import asyncio
        from api.ai.governance import validate_ai_output, log_ai_call
        from api.ai.persistence import save_comprehensive_analysis
        from api.ai.feature_engineering import FeatureEngineer
        
        # Prepare features
        feature_engineer = FeatureEngineer()
        features = feature_engineer.create_feature_vector(patient_data)
        features['patient_id'] = str(patient_id)
        
        # Run in parallel
        try:
            analysis_output = asyncio.run(orchestrator.analyze_patient_comprehensive_parallel(
                patient_data=patient_data,
                features=features,
                include_similarity=True,
                include_referral=True
            ))
            
            # Validate output
            is_valid, error = validate_ai_output('comprehensive', analysis_output)
            if not is_valid:
                raise ValueError(f"AI Output Validation Failed: {error}")
                
        except Exception as e:
            logger.error(f"Parallel analysis failed, falling back: {e}")
            analysis_output = orchestrator.analyze_patient_comprehensive(
                patient_id=str(patient_id),
                patient_data=patient_data,
                include_similarity=True,
                include_referral=True
            )

        if job:
            job.update_progress(85, "Saving results")

        # Save results atomically
        performed_by = User.objects.get(id=user_id) if user_id else None
        analysis = save_comprehensive_analysis(
            patient=patient,
            hospital=patient.registered_at,
            user=performed_by,
            analysis_result=analysis_output
        )

        # Log for governance
        log_ai_call(
            user=performed_by,
            hospital=patient.registered_at,
            analysis_type='comprehensive',
            input_summary=f"Patient {patient_id} comprehensive analysis",
            output_summary=analysis_output.get('clinical_summary', ''),
            model_version='1.1.0-hardened',
            confidence=analysis_output.get('confidence_score'),
            latency_ms=analysis_output.get('metrics', {}).get('total_duration_ms')
        )

        # Results are already saved atomically by save_comprehensive_analysis

        # Mark job as complete
        if job:
            job.mark_completed(analysis)

        logger.info(f"Successfully completed AI analysis for patient {patient_id}, job {job_id}")
        return {
            "status": "success",
            "patient_id": str(patient_id),
            "analysis_id": str(analysis.id),
            "job_id": str(job_id) if job_id else None,
            "analysis_type": analysis_type,
            "confidence_score": analysis.overall_confidence
        }

    except Exception as exc:
        logger.error(f"Error running AI analysis for patient {patient_id}: {exc}")

        # Mark job as failed
        if job_id:
            try:
                job = AIAnalysisJob.objects.get(id=job_id)
                job.mark_failed(str(exc))
            except BaseException:
                pass

        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=5 ** self.request.retries)


@shared_task(bind=True, max_retries=3)
def risk_prediction_task(self, patient_id, job_id=None, user_id=None, disease_types=None):
    """
    Async task to run disease risk prediction for a patient.

    Args:
        patient_id: UUID of patient
        job_id: UUID of AIAnalysisJob (for progress tracking)
        user_id: UUID of user who requested analysis
        disease_types: List of disease types to predict (or None for all)

    Returns:
        dict with risk scores
    """
    try:
        from patients.models import Patient
        from api.models import AIAnalysisJob, AIAnalysis
        from core.models import User
        from api.ai.services.services import RiskPredictionService
        from api.ai.processors import DataProcessor

        patient = Patient.objects.get(id=patient_id)

        job = None
        if job_id:
            try:
                job = AIAnalysisJob.objects.get(id=job_id)
                job.mark_processing()
            except BaseException as e:
                logger.debug(f"Could not mark job {job_id} as processing: {str(e)}")

        logger.info(f"Running risk prediction for patient {patient_id}, job {job_id}")

        if job:
            job.update_progress(15, "Extracting clinical data")

        # Extract data
        data_processor = DataProcessor()
        patient_data = data_processor.extract_patient_data(patient)

        if job:
            job.update_progress(40, "Running risk prediction model")

        # Run risk prediction
        risk_service = RiskPredictionService(user=User.objects.get(id=user_id) if user_id else None)
        predictions = risk_service.predict_disease_risk(patient_data, disease_types)

        if job:
            job.update_progress(80, "Saving predictions")

        # Save results atomically using unified persistence layer
        from api.ai.persistence import save_risk_prediction
        analysis = save_risk_prediction(
            patient=patient,
            hospital=patient.registered_at,
            user=User.objects.get(id=user_id) if user_id else None,
            prediction_result=predictions
        )

        if job:
            job.mark_completed(analysis)

        logger.info(f"Risk prediction completed for patient {patient_id}")
        return {
            "status": "success",
            "patient_id": str(patient_id),
            "analysis_id": str(analysis.id),
            "predictions_count": len(predictions.get('predictions', {}))
        }

    except Exception as exc:
        logger.error(f"Error in risk prediction for patient {patient_id}: {exc}")

        raise self.retry(exc=exc, countdown=5 ** self.request.retries)

        if job_id:
            try:
                job = AIAnalysisJob.objects.get(id=job_id)
                job.mark_failed(str(exc))
            except BaseException as e:
                logger.debug(f"Could not update job {job_id} failure status: {str(e)}")


# Persistence is now handled by api.ai.persistence module

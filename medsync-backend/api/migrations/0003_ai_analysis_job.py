# Generated migration for AIAnalysisJob model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_rename_ai_analysis_patient_created_idx_ai_analysis_patient_34fc3'
         '9_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIAnalysisJob',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('celery_task_id', models.CharField(blank=True, help_text='Celery task ID for tracking', max_length=255, null=True, unique=True)),
                ('analysis_type', models.CharField(choices=[('comprehensive', 'Comprehensive Multi-Agent Analysis'), ('risk_prediction', 'Disease Risk Prediction'), ('clinical_decision_support', 'Clinical Decision Support'), ('triage', 'Patient Triage'), ('similarity_search', 'Similar Patient Search'), ('referral', 'Hospital Referral Recommendation')], max_length=50)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='pending', max_length=20)),
                ('progress_percent', models.IntegerField(default=0, help_text='0-100')),
                ('current_step', models.CharField(blank=True, help_text="Current processing step (e.g., 'Running data agent')", max_length=100)),
                ('error_message', models.TextField(blank=True, help_text='Error message if job failed')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('analysis_result', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='job', to='api.aianalysis')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('hospital', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='ai_jobs', to='core.hospital')),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_jobs', to='patients.patient')),
            ],
            options={
                'db_table': 'api_ai_analysis_job',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='aianalysisjob',
            index=models.Index(fields=['patient', '-created_at'], name='api_ai_patient_created_idx'),
        ),
        migrations.AddIndex(
            model_name='aianalysisjob',
            index=models.Index(fields=['hospital', '-created_at'], name='api_ai_hospital_created_idx'),
        ),
        migrations.AddIndex(
            model_name='aianalysisjob',
            index=models.Index(fields=['status', '-created_at'], name='api_ai_status_created_idx'),
        ),
        migrations.AddIndex(
            model_name='aianalysisjob',
            index=models.Index(fields=['celery_task_id'], name='api_ai_celery_task_idx'),
        ),
    ]

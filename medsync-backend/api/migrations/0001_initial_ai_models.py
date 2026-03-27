"""
Initial AI Analysis models migration.

Creates tables:
- ai_analysis
- disease_risk_prediction
- diagnosis_suggestion
- triage_assessment
- patient_similarity_match
- referral_recommendation
- ai_analysis_counter
"""

from django.db import migrations, models
import django.db.models.deletion
import uuid
import django.contrib.postgres.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0003_blueprint_alerts_encounters'),  # Dependency on core.Hospital, core.User
        ('patients', '0001_blueprint_alerts_encounters'),  # Dependency on patients.Patient
    ]

    operations = [
        migrations.CreateModel(
            name='AIAnalysis',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('analysis_type', models.CharField(choices=[('comprehensive', 'Comprehensive Multi-Agent Analysis'), ('risk_prediction', 'Disease Risk Prediction'), ('clinical_decision_support', 'Clinical Decision Support'), ('triage', 'Patient Triage'), ('similarity_search', 'Similar Patient Search'), ('referral', 'Hospital Referral Recommendation')], default='comprehensive', max_length=50)),
                ('overall_confidence', models.FloatField(default=0.0, help_text='0-1 confidence score')),
                ('agents_executed', models.JSONField(default=list, help_text='Names of AI agents that executed')),
                ('clinical_summary', models.TextField(blank=True)),
                ('recommended_actions', models.JSONField(default=list, help_text='List of recommended clinical actions')),
                ('alerts', models.JSONField(default=list, help_text='Clinical alerts generated')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('chief_complaint', models.TextField(blank=True)),
                ('additional_context', models.JSONField(blank=True, default=dict)),
                ('hospital', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='ai_analyses', to='core.hospital')),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_analyses', to='patients.patient')),
                ('performed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.user')),
            ],
            options={
                'db_table': 'ai_analysis',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='DiseaseRiskPrediction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('disease', models.CharField(choices=[('heart_disease', 'Heart Disease'), ('diabetes', 'Diabetes Mellitus'), ('stroke', 'Stroke (CVA)'), ('pneumonia', 'Pneumonia'), ('hypertension', 'Hypertension'), ('kidney_disease', 'Kidney Disease'), ('copd', 'COPD'), ('asthma', 'Asthma'), ('cancer', 'Cancer')], max_length=50)),
                ('risk_score', models.FloatField(help_text='0-100 scale')),
                ('risk_category', models.CharField(choices=[('low', 'Low Risk (0-20%)'), ('medium', 'Medium Risk (20-50%)'), ('high', 'High Risk (50-80%)'), ('critical', 'Critical Risk (80%+)')], max_length=20)),
                ('confidence', models.FloatField(help_text='0-1 confidence')),
                ('contributing_factors', models.JSONField(blank=True, default=list, help_text='List of factors that contributed to this prediction')),
                ('recommendations', django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), blank=True, default=list, help_text='Clinical recommendations for this disease', size=None)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('analysis', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='disease_predictions', to='api.aianalysis')),
            ],
            options={
                'db_table': 'disease_risk_prediction',
                'ordering': ['-risk_score'],
                'unique_together': {('analysis', 'disease')},
            },
        ),
        migrations.CreateModel(
            name='DiagnosisSuggestion',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('rank', models.IntegerField(help_text='Ranking among suggestions (1=most likely)')),
                ('diagnosis', models.CharField(max_length=200)),
                ('icd10_code', models.CharField(blank=True, max_length=10)),
                ('probability', models.FloatField(help_text='0-1 likelihood')),
                ('confidence', models.FloatField(help_text='0-1 model confidence')),
                ('matching_symptoms', models.JSONField(blank=True, default=list)),
                ('recommended_tests', models.JSONField(blank=True, default=list)),
                ('clinical_notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('analysis', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='diagnosis_suggestions', to='api.aianalysis')),
            ],
            options={
                'db_table': 'diagnosis_suggestion',
                'ordering': ['analysis', 'rank'],
            },
        ),
        migrations.CreateModel(
            name='TriageAssessment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('triage_level', models.CharField(choices=[('critical', 'Critical (Immediate)'), ('high', 'High (Urgent)'), ('medium', 'Medium (Soon)'), ('low', 'Low (Routine)')], max_length=20)),
                ('triage_score', models.FloatField(help_text='0-100 scale')),
                ('confidence', models.FloatField(help_text='0-1 confidence')),
                ('esi_level', models.IntegerField(help_text='Emergency Severity Index (1-5)')),
                ('reason', models.TextField()),
                ('indicators', models.JSONField(blank=True, default=list, help_text='List of indicators that determined triage level')),
                ('recommended_action', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('analysis', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='triage_assessment', to='api.aianalysis')),
            ],
            options={
                'db_table': 'triage_assessment',
                'ordering': ['analysis', '-triage_score'],
            },
        ),
        migrations.CreateModel(
            name='PatientSimilarityMatch',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('rank', models.IntegerField(help_text='Ranking by similarity (1=most similar)')),
                ('similarity_score', models.FloatField(help_text='0-1 similarity')),
                ('matching_conditions', models.JSONField(blank=True, default=list)),
                ('treatment_outcome', models.CharField(blank=True, max_length=200)),
                ('outcome_success_rate', models.FloatField(blank=True, help_text='0-1 success rate', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('analysis', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='similar_patients', to='api.aianalysis')),
                ('similar_patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='similarity_matches', to='patients.patient')),
            ],
            options={
                'db_table': 'patient_similarity_match',
                'ordering': ['analysis', 'rank'],
                'unique_together': {('analysis', 'similar_patient')},
            },
        ),
        migrations.CreateModel(
            name='ReferralRecommendation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('rank', models.IntegerField(help_text='Ranking by suitability (1=best match)')),
                ('specialty_match', models.FloatField(help_text='0-1 specialty match score')),
                ('bed_availability', models.IntegerField(blank=True, null=True)),
                ('distance_km', models.FloatField(blank=True, null=True)),
                ('success_rate', models.FloatField(blank=True, help_text='0-1 treatment success rate', null=True)),
                ('reason', models.TextField(help_text='Why this hospital is recommended')),
                ('referral_created', models.BooleanField(default=False)),
                ('referral_accepted', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('analysis', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='referral_recommendations', to='api.aianalysis')),
                ('recommended_hospital', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='referral_recommendations', to='core.hospital')),
            ],
            options={
                'db_table': 'referral_recommendation',
                'ordering': ['analysis', 'rank'],
                'unique_together': {('analysis', 'recommended_hospital')},
            },
        ),
        migrations.CreateModel(
            name='AIAnalysisCounter',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('date', models.DateField(db_index=True)),
                ('total_analyses', models.IntegerField(default=0)),
                ('risk_predictions', models.IntegerField(default=0)),
                ('cds_queries', models.IntegerField(default=0)),
                ('triage_assessments', models.IntegerField(default=0)),
                ('similarity_searches', models.IntegerField(default=0)),
                ('referral_recommendations', models.IntegerField(default=0)),
                ('avg_confidence', models.FloatField(default=0.0)),
                ('total_alerts_generated', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('hospital', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_analysis_counters', to='core.hospital')),
            ],
            options={
                'db_table': 'ai_analysis_counter',
                'ordering': ['-date'],
                'unique_together': {('hospital', 'date')},
            },
        ),
        migrations.AddIndex(
            model_name='aianalysis',
            index=models.Index(fields=['patient', '-created_at'], name='ai_analysis_patient_created_idx'),
        ),
        migrations.AddIndex(
            model_name='aianalysis',
            index=models.Index(fields=['hospital', '-created_at'], name='ai_analysis_hospital_created_idx'),
        ),
        migrations.AddIndex(
            model_name='aianalysis',
            index=models.Index(fields=['analysis_type', '-created_at'], name='ai_analysis_type_created_idx'),
        ),
        migrations.AddIndex(
            model_name='diseaseriskprediction',
            index=models.Index(fields=['analysis', '-risk_score'], name='disease_risk_analysis_score_idx'),
        ),
        migrations.AddIndex(
            model_name='diagnosissuggestion',
            index=models.Index(fields=['analysis', 'rank'], name='diagnosis_analysis_rank_idx'),
        ),
        migrations.AddIndex(
            model_name='patientsimilaritymatch',
            index=models.Index(fields=['analysis', 'rank'], name='similarity_analysis_rank_idx'),
        ),
        migrations.AddIndex(
            model_name='patientsimilaritymatch',
            index=models.Index(fields=['similar_patient'], name='similarity_similar_patient_idx'),
        ),
        migrations.AddIndex(
            model_name='referralrecommendation',
            index=models.Index(fields=['analysis', 'rank'], name='referral_analysis_rank_idx'),
        ),
        migrations.AddIndex(
            model_name='referralrecommendation',
            index=models.Index(fields=['recommended_hospital'], name='referral_hospital_idx'),
        ),
        migrations.AddIndex(
            model_name='aianalysiscounter',
            index=models.Index(fields=['hospital', '-date'], name='ai_counter_hospital_date_idx'),
        ),
    ]

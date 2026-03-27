# Workflow: LabTestType, Encounter routing fields, LabOrder lab_unit + status

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("records", "0002_encounter"),
        ("core", "0005_workflow_department_lab_unit"),
    ]

    operations = [
        migrations.CreateModel(
            name="LabTestType",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("test_name", models.CharField(max_length=200)),
                ("specimen", models.CharField(blank=True, default="", max_length=80)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("lab_unit", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="core.labunit")),
            ],
            options={
                "unique_together": {("lab_unit", "test_name")},
            },
        ),
        migrations.AddField(
            model_name="encounter",
            name="assigned_department",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="encounters",
                to="core.department",
            ),
        ),
        migrations.AddField(
            model_name="encounter",
            name="assigned_doctor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_encounters",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="encounter",
            name="status",
            field=models.CharField(
                choices=[
                    ("waiting", "Waiting"),
                    ("in_consultation", "In Consultation"),
                    ("completed", "Completed"),
                ],
                default="waiting",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="laborder",
            name="lab_unit",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="orders",
                to="core.labunit",
            ),
        ),
        migrations.AddField(
            model_name="laborder",
            name="status",
            field=models.CharField(
                choices=[
                    ("ordered", "Ordered"),
                    ("collected", "Specimen Collected"),
                    ("in_progress", "In Progress"),
                    ("completed", "Completed"),
                ],
                default="ordered",
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name="encounter",
            index=models.Index(fields=["assigned_department", "status"], name="records_enc_dept_st_idx"),
        ),
        migrations.AddIndex(
            model_name="encounter",
            index=models.Index(fields=["assigned_doctor", "status"], name="records_enc_doc_st_idx"),
        ),
    ]

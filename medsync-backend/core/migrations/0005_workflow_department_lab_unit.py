# Workflow: Department, LabUnit, User.department_link, User.lab_unit

import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_audit_log_chain_hash_default"),
    ]

    operations = [
        migrations.CreateModel(
            name="Department",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("hospital", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="core.hospital")),
            ],
            options={
                "unique_together": {("hospital", "name")},
            },
        ),
        migrations.CreateModel(
            name="LabUnit",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("hospital", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="core.hospital")),
            ],
            options={
                "unique_together": {("hospital", "name")},
            },
        ),
        migrations.AddField(
            model_name="user",
            name="department_link",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="users",
                to="core.department",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="lab_unit",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="technicians",
                to="core.labunit",
            ),
        ),
    ]

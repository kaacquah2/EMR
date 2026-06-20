from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("records", "0025_remove_prescription_dispense_workflow_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="radiologyorder",
            name="findings",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Radiologist narrative findings / report text.",
            ),
        ),
        migrations.AddField(
            model_name="radiologyorder",
            name="reported_by",
            field=models.ForeignKey(
                blank=True,
                help_text="Technician who finalized the report.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="radiology_reports",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="radiologyorder",
            name="reported_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

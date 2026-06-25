from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0017_remove_ai_models"),
        ("records", "0025_remove_prescription_dispense_workflow_and_more"),
    ]

    operations = [
        # CdsAlert.encounter: CASCADE → PROTECT (encounter deletion blocked while CDS alerts exist)
        migrations.AlterField(
            model_name="cdsalert",
            name="encounter",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cds_alerts",
                to="records.encounter",
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0014_alter_dispensation_prescription"),
    ]

    operations = [
        migrations.AddField(
            model_name="aianalysisjob",
            name="result_data",
            field=models.JSONField(blank=True, help_text="Raw task result payload", null=True),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("records", "0008_nursingnote_handover_signatures"),
    ]

    operations = [
        migrations.AlterField(
            model_name="laborder",
            name="status",
            field=models.CharField(
                choices=[
                    ("ordered", "Ordered"),
                    ("collected", "Specimen Collected"),
                    ("in_progress", "In Progress"),
                    ("resulted", "Resulted"),
                    ("verified", "Verified"),
                ],
                default="ordered",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="laborder",
            name="collection_time",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="laborder",
            name="started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="laborder",
            name="resulted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="laborder",
            name="verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

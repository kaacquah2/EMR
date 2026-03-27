from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0019_user_last_role_reviewed_at"),
        ("records", "0007_nurseshift_shifthandover_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="nursingnote",
            name="acknowledged_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="nursingnote",
            name="acknowledged_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="acknowledged_handover_notes",
                to="core.user",
            ),
        ),
        migrations.AddField(
            model_name="nursingnote",
            name="incoming_nurse",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="incoming_handover_notes",
                to="core.user",
            ),
        ),
        migrations.AddField(
            model_name="nursingnote",
            name="note_type",
            field=models.CharField(
                choices=[("observation", "Observation"), ("handover", "Handover"), ("incident", "Incident")],
                default="observation",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="nursingnote",
            name="outgoing_signed_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
            preserve_default=False,
        ),
    ]

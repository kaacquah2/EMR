from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0039_remove_tasksubmission_userpushsubscription"),
        ("interop", "0014_consent_consented_encounter_ids_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="referral",
            name="from_facility",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="referrals_sent",
                to="core.hospital",
            ),
        ),
        migrations.AlterField(
            model_name="referral",
            name="to_facility",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="referrals_received",
                to="core.hospital",
            ),
        ),
    ]

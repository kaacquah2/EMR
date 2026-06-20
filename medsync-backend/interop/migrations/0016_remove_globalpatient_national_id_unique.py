"""
Remove the DB-level UNIQUE constraint from GlobalPatient.national_id.

The field is non-deterministically encrypted (Fernet via django-cryptography),
so each encryption of the same plaintext produces different ciphertext.  A DB
UNIQUE constraint on a ciphertext column therefore never catches duplicate
plaintext values — it only prevents the same ciphertext byte-sequence from
appearing twice, which effectively never happens.

Application-level uniqueness is now enforced in GlobalPatient.save().
"""

from django.db import migrations, models
import django_cryptography.fields


class Migration(migrations.Migration):

    dependencies = [
        ("interop", "0015_rename_encounter_facilityencounter_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="globalpatient",
            name="national_id",
            # Remove unique=True — uniqueness is now enforced in GlobalPatient.save()
            # via Python-level comparison after decryption.
            field=django_cryptography.fields.encrypt(
                models.CharField(blank=True, max_length=50, null=True)
            ),
        ),
    ]

from django.db import migrations


class Migration(migrations.Migration):
    """
    Remove Hospital.ai_enabled — the AI subsystem was removed in 0017_remove_ai_models.
    The field has no application-code readers or writers; removing it cleans up the schema.
    """

    dependencies = [
        ("core", "0040_fix_cascade_on_delete"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="hospital",
            name="ai_enabled",
        ),
    ]

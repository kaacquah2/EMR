from django.db import migrations, models


def paid_amount_decimal_to_cents(apps, schema_editor):
    Invoice = apps.get_model("patients", "Invoice")
    for invoice in Invoice.objects.all():
        # paid_amount was a DecimalField (e.g. 150.50 GHS); convert to integer cents
        old_val = invoice.paid_amount or 0
        invoice.paid_amount_cents = int(round(float(old_val) * 100))
        invoice.save(update_fields=["paid_amount_cents"])


def cents_to_paid_amount_decimal(apps, schema_editor):
    Invoice = apps.get_model("patients", "Invoice")
    for invoice in Invoice.objects.all():
        from decimal import Decimal
        invoice.paid_amount = Decimal(invoice.paid_amount_cents) / 100
        invoice.save(update_fields=["paid_amount"])


class Migration(migrations.Migration):
    """
    Standardise Invoice money representation: replace DecimalField paid_amount
    with IntegerField paid_amount_cents (matching amount_cents / unit_price).
    A paid_amount property on the model provides the Decimal view for compat.
    """

    dependencies = [
        ("patients", "0018_remove_patient_user"),
    ]

    operations = [
        # Step 1: add new column with default 0
        migrations.AddField(
            model_name="invoice",
            name="paid_amount_cents",
            field=models.IntegerField(default=0),
        ),
        # Step 2: migrate data (old DecimalField → integer cents)
        migrations.RunPython(
            paid_amount_decimal_to_cents,
            reverse_code=cents_to_paid_amount_decimal,
        ),
        # Step 3: drop the old column
        migrations.RemoveField(
            model_name="invoice",
            name="paid_amount",
        ),
    ]

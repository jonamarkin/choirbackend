from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0007_directdebit_consecutive_failed_charges_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="paymenttransaction",
            constraint=models.UniqueConstraint(
                condition=(
                    models.Q(("direct_debit__isnull", False))
                    & models.Q(("status__in", ["initiated", "pending"]))
                ),
                fields=("direct_debit",),
                name="uniq_inflight_tx_per_direct_debit",
            ),
        ),
    ]

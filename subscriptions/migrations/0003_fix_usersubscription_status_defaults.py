from django.db import migrations, models


def normalize_usersubscription_statuses(apps, schema_editor):
    UserSubscription = apps.get_model('subscriptions', 'UserSubscription')
    UserSubscription.objects.filter(status='pending').update(status='not_paid')
    UserSubscription.objects.filter(status='active').update(status='partially_paid')


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0002_alter_usersubscription_status_paymenttransaction'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usersubscription',
            name='status',
            field=models.CharField(
                choices=[
                    ('fully_paid', 'Fully Paid'),
                    ('partially_paid', 'Partially Paid'),
                    ('overdue', 'Overdue'),
                    ('not_paid', 'Not Paid'),
                    ('refunded', 'Refunded'),
                ],
                default='not_paid',
                max_length=20,
            ),
        ),
        migrations.RunPython(
            normalize_usersubscription_statuses,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

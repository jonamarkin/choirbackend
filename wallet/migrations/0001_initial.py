import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MobileWallet',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, help_text='Optional description of the wallet', null=True)),
                ('network', models.CharField(choices=[('MTN', 'MTN'), ('TELECEL', 'TELECEL'), ('AIRTELTIGO', 'AIRTELTIGO')], max_length=20)),
                ('account_number', models.CharField(max_length=20, unique=True)),
                ('is_active', models.BooleanField(default=True)),
                ('verified_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wallets', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'mobile_wallets',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='mobilewallet',
            index=models.Index(fields=['user', 'is_active'], name='mobile_wall_user_id_d3ef80_idx'),
        ),
        migrations.AddIndex(
            model_name='mobilewallet',
            index=models.Index(fields=['account_number'], name='mobile_wall_account_0bb9d2_idx'),
        ),
    ]

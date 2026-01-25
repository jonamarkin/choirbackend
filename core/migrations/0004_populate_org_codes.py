import random
from django.db import migrations

def gen_unique_code(apps):
    Organization = apps.get_model('core', 'Organization')
    while True:
        code = str(random.randint(1000, 9999))
        if not Organization.objects.filter(code=code).exists():
            return code

def populate_codes(apps, schema_editor):
    Organization = apps.get_model('core', 'Organization')
    for org in Organization.objects.filter(code__isnull=True):
        org.code = gen_unique_code(apps)
        org.save()

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_organization_code'),
    ]

    operations = [
        migrations.RunPython(populate_codes),
    ]

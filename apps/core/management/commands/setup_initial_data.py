from django.core.management.base import BaseCommand
from apps.core.models import Organization
from apps.authentication.models import User


class Command(BaseCommand):
    help = 'Setup initial organization and admin user'

    def handle(self, *args, **options):
        # Create organization
        org, created = Organization.objects.get_or_create(
            slug='vocalessence',
            defaults={
                'name': 'VocalEssence Chorale',
                'contact_email': 'info@vocalessence.com',
                'contact_phone': '+233244123456'
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'✅ Created organization: {org.name}'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠️  Organization already exists: {org.name}'))
        
        # Create admin user
        if not User.objects.filter(username='admin').exists():
            admin_user = User.objects.create_superuser(
                username='admin',
                email='admin@vocalessence.com',
                password='admin123',  # Change this!
                organization=org,
                role='super_admin'
            )
            self.stdout.write(self.style.SUCCESS(f'✅ Created admin user: {admin_user.username}'))
            self.stdout.write(self.style.SUCCESS(f'   Username: admin'))
            self.stdout.write(self.style.SUCCESS(f'   Password: admin123'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Admin user already exists'))
        
        self.stdout.write(self.style.SUCCESS('\n🎉 Setup complete!'))
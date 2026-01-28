"""
Management command to assign missing subscriptions to existing users.

This is a one-time fix for users who were created after subscriptions
but before the auto-assignment signal was added.

Usage:
    python manage.py assign_missing_subscriptions
    python manage.py assign_missing_subscriptions --dry-run
    python manage.py assign_missing_subscriptions --organization=ORG_CODE
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from subscriptions.models import Subscription, UserSubscription

User = get_user_model()


class Command(BaseCommand):
    help = 'Assign missing subscriptions to existing users based on their role and organization'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--organization',
            type=str,
            help='Only process users from a specific organization (by code)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        org_code = options.get('organization')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made\n'))

        # Executive roles for category matching
        executive_roles = ['super_admin', 'admin', 'finance_admin', 'attendance_officer', 'treasurer']

        # Get users to process
        users = User.objects.filter(
            organization__isnull=False,
            is_active=True
        ).select_related('organization')

        if org_code:
            users = users.filter(organization__code=org_code)
            self.stdout.write(f'Filtering to organization: {org_code}\n')

        total_users = users.count()
        self.stdout.write(f'Processing {total_users} users...\n')

        total_created = 0
        users_updated = 0

        for user in users:
            # Get all active subscriptions for user's organization
            active_subscriptions = Subscription.objects.filter(
                organization=user.organization,
                is_active=True
            )

            is_executive = user.role in executive_roles
            user_subs_created = 0

            for subscription in active_subscriptions:
                # Check eligibility based on assignees_category
                if subscription.assignees_category == 'EXECUTIVES' and not is_executive:
                    continue
                elif subscription.assignees_category == 'MEMBERS' and is_executive:
                    continue
                # 'BOTH' applies to everyone

                # Check if user already has this subscription
                if not UserSubscription.objects.filter(user=user, subscription=subscription).exists():
                    if not dry_run:
                        UserSubscription.objects.create(
                            user=user,
                            subscription=subscription,
                            status='not_paid'
                        )
                    user_subs_created += 1
                    total_created += 1

            if user_subs_created > 0:
                users_updated += 1
                self.stdout.write(
                    f'  {user.email}: +{user_subs_created} subscription(s)'
                )

        self.stdout.write('\n' + '=' * 50)
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'DRY RUN COMPLETE\n'
                f'Would create {total_created} UserSubscription records\n'
                f'Would affect {users_updated} users'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'COMPLETE\n'
                f'Created {total_created} UserSubscription records\n'
                f'Updated {users_updated} users'
            ))

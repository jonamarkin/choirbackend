from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.test.client import RequestFactory
from datetime import date, timedelta
from core.models import Organization
from subscriptions.models import Subscription, UserSubscription, PaymentTransaction
from subscriptions.views.subscription_views import SubscriptionViewSet

User = get_user_model()


class SubscriptionAssignmentSignalTests(TestCase):
    """Test automatic subscription assignment signals."""
    
    def setUp(self):
        """Set up test data."""
        self.organization = Organization.objects.create(
            name="Test Church",
            code="TEST"
        )
        
        # Dates for subscriptions
        self.today = date.today()
        self.next_year = self.today + timedelta(days=365)
    
    def test_subscription_assigned_to_existing_users_on_creation(self):
        """Test that when a subscription is created, it's assigned to existing users."""
        # Create users first
        member = User.objects.create_user(
            username="member1",
            email="member1@test.com",
            password="password123",
            organization=self.organization,
            role="member"
        )
        admin = User.objects.create_user(
            username="admin1",
            email="admin1@test.com",
            password="password123",
            organization=self.organization,
            role="admin"
        )
        
        # Create a subscription for BOTH
        subscription = Subscription.objects.create(
            name="Annual Dues 2024",
            description="Annual membership dues",
            amount=100.00,
            start_date=self.today,
            end_date=self.next_year,
            organization=self.organization,
            assignees_category="BOTH",
            is_active=True
        )
        
        # Both users should have the subscription
        self.assertTrue(
            UserSubscription.objects.filter(user=member, subscription=subscription).exists(),
            "Member should be assigned to BOTH subscription"
        )
        self.assertTrue(
            UserSubscription.objects.filter(user=admin, subscription=subscription).exists(),
            "Admin should be assigned to BOTH subscription"
        )
    
    def test_new_user_assigned_to_existing_subscriptions(self):
        """Test that when a new user is created, they get assigned to existing active subscriptions."""
        # Create subscription first
        subscription = Subscription.objects.create(
            name="Annual Dues 2024",
            description="Annual membership dues",
            amount=100.00,
            start_date=self.today,
            end_date=self.next_year,
            organization=self.organization,
            assignees_category="BOTH",
            is_active=True
        )
        
        # Create user after subscription exists
        member = User.objects.create_user(
            username="new_member",
            email="new_member@test.com",
            password="password123",
            organization=self.organization,
            role="member"
        )
        
        # New user should have the subscription
        self.assertTrue(
            UserSubscription.objects.filter(user=member, subscription=subscription).exists(),
            "New user should be assigned to existing subscription"
        )
        
        # Check status is not_paid
        user_sub = UserSubscription.objects.get(user=member, subscription=subscription)
        self.assertEqual(user_sub.status, "not_paid")

    def test_user_gets_assigned_when_organization_is_set_after_creation(self):
        """
        Regression: user may be created first, then organization is attached later.
        Subscriptions should still be backfilled after org assignment.
        """
        subscription = Subscription.objects.create(
            name="Annual Dues 2024",
            description="Annual membership dues",
            amount=100.00,
            start_date=self.today,
            end_date=self.next_year,
            organization=self.organization,
            assignees_category="BOTH",
            is_active=True
        )

        user = User.objects.create_user(
            username="late_org_member",
            email="late_org_member@test.com",
            password="password123",
            organization=None,
            role="member"
        )
        self.assertFalse(
            UserSubscription.objects.filter(user=user, subscription=subscription).exists()
        )

        user.organization = self.organization
        user.save(update_fields=["organization"])

        self.assertTrue(
            UserSubscription.objects.filter(user=user, subscription=subscription).exists(),
            "User should be assigned once organization is attached"
        )
    
    def test_executives_only_subscription(self):
        """Test EXECUTIVES category only applies to executive roles."""
        # Create executives-only subscription
        exec_subscription = Subscription.objects.create(
            name="Executive Fee",
            description="Fee for executives only",
            amount=50.00,
            start_date=self.today,
            end_date=self.next_year,
            organization=self.organization,
            assignees_category="EXECUTIVES",
            is_active=True
        )
        
        # Create an admin (executive) user
        admin = User.objects.create_user(
            username="exec_admin",
            email="exec_admin@test.com",
            password="password123",
            organization=self.organization,
            role="admin"
        )
        
        # Create a regular member
        member = User.objects.create_user(
            username="regular_member",
            email="regular_member@test.com",
            password="password123",
            organization=self.organization,
            role="member"
        )
        
        # Admin should have the subscription
        self.assertTrue(
            UserSubscription.objects.filter(user=admin, subscription=exec_subscription).exists(),
            "Executive should be assigned to EXECUTIVES subscription"
        )
        
        # Member should NOT have the subscription
        self.assertFalse(
            UserSubscription.objects.filter(user=member, subscription=exec_subscription).exists(),
            "Regular member should NOT be assigned to EXECUTIVES subscription"
        )
    
    def test_members_only_subscription(self):
        """Test MEMBERS category only applies to regular members."""
        # Create members-only subscription
        member_subscription = Subscription.objects.create(
            name="Member Fee",
            description="Fee for members only",
            amount=25.00,
            start_date=self.today,
            end_date=self.next_year,
            organization=self.organization,
            assignees_category="MEMBERS",
            is_active=True
        )
        
        # Create an admin (executive) user
        admin = User.objects.create_user(
            username="admin_user",
            email="admin_user@test.com",
            password="password123",
            organization=self.organization,
            role="admin"
        )
        
        # Create a regular member
        member = User.objects.create_user(
            username="member_user",
            email="member_user@test.com",
            password="password123",
            organization=self.organization,
            role="member"
        )
        
        # Member should have the subscription
        self.assertTrue(
            UserSubscription.objects.filter(user=member, subscription=member_subscription).exists(),
            "Regular member should be assigned to MEMBERS subscription"
        )
        
        # Admin should NOT have the subscription
        self.assertFalse(
            UserSubscription.objects.filter(user=admin, subscription=member_subscription).exists(),
            "Executive should NOT be assigned to MEMBERS subscription"
        )
    
    def test_inactive_subscription_not_assigned_to_new_users(self):
        """Test that inactive subscriptions are not assigned to new users."""
        # Create an inactive subscription
        inactive_subscription = Subscription.objects.create(
            name="Old Subscription",
            description="This is inactive",
            amount=100.00,
            start_date=self.today,
            end_date=self.next_year,
            organization=self.organization,
            assignees_category="BOTH",
            is_active=False
        )
        
        # Create user after subscription exists
        member = User.objects.create_user(
            username="late_member",
            email="late_member@test.com",
            password="password123",
            organization=self.organization,
            role="member"
        )
        
        # New user should NOT have the inactive subscription
        self.assertFalse(
            UserSubscription.objects.filter(user=member, subscription=inactive_subscription).exists(),
            "New user should NOT be assigned to inactive subscription"
        )
    
    def test_user_without_organization_not_assigned(self):
        """Test that users without an organization don't get subscriptions."""
        # Create subscription
        subscription = Subscription.objects.create(
            name="Annual Dues",
            description="Annual dues",
            amount=100.00,
            start_date=self.today,
            end_date=self.next_year,
            organization=self.organization,
            assignees_category="BOTH",
            is_active=True
        )
        
        # Create user without organization
        user = User.objects.create_user(
            username="no_org_user",
            email="no_org@test.com",
            password="password123",
            organization=None,
            role="member"
        )
        
        # User should NOT have any subscriptions
        self.assertFalse(
            UserSubscription.objects.filter(user=user).exists(),
            "User without organization should not get any subscriptions"
        )
    
    def test_all_executive_roles_get_executives_subscription(self):
        """Test that all executive roles are assigned to EXECUTIVES subscriptions."""
        # Create executives-only subscription
        exec_subscription = Subscription.objects.create(
            name="Executive Fee",
            description="Fee for executives",
            amount=50.00,
            start_date=self.today,
            end_date=self.next_year,
            organization=self.organization,
            assignees_category="EXECUTIVES",
            is_active=True
        )
        
        executive_roles = ['super_admin', 'admin', 'finance_admin', 'attendance_officer', 'treasurer']
        
        for role in executive_roles:
            user = User.objects.create_user(
                username=f"exec_{role}",
                email=f"exec_{role}@test.com",
                password="password123",
                organization=self.organization,
                role=role
            )
            
            self.assertTrue(
                UserSubscription.objects.filter(user=user, subscription=exec_subscription).exists(),
                f"User with role '{role}' should be assigned to EXECUTIVES subscription"
            )


class UserSubscriptionBehaviorTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Behavior Org",
            code="B001",
        )
        self.user = User.objects.create_user(
            username="behavior_user",
            email="behavior@test.com",
            password="password123",
            organization=self.organization,
            role="member",
        )
        self.subscription = Subscription.objects.create(
            name="Behavior Subscription",
            description="Behavior checks",
            amount=100.00,
            start_date=date.today() - timedelta(days=1),
            end_date=date.today() + timedelta(days=20),
            organization=self.organization,
            assignees_category="BOTH",
            is_active=True,
        )
        self.user_subscription = UserSubscription.objects.get(
            user=self.user,
            subscription=self.subscription,
        )

    def test_is_currently_active_uses_supported_paid_statuses(self):
        self.user_subscription.status = 'partially_paid'
        self.user_subscription.save(update_fields=['status'])
        self.assertTrue(self.user_subscription.is_currently_active())

        self.user_subscription.status = 'not_paid'
        self.user_subscription.save(update_fields=['status'])
        self.assertFalse(self.user_subscription.is_currently_active())

    def test_can_make_payment_blocks_recent_pending_for_five_minutes(self):
        tx = PaymentTransaction.objects.create(
            user_subscription=self.user_subscription,
            user=self.user,
            organization=self.organization,
            client_reference="test-ref-1",
            amount=10,
            description="test",
            status='initiated',
        )
        tx.created_at = timezone.now() - timedelta(minutes=4)
        tx.save(update_fields=['created_at'])

        can_pay, message = self.user_subscription.can_make_payment()
        self.assertFalse(can_pay)
        self.assertIn('5 minutes', message)

        tx.created_at = timezone.now() - timedelta(minutes=6)
        tx.save(update_fields=['created_at'])
        can_pay_after_window, _ = self.user_subscription.can_make_payment()
        self.assertTrue(can_pay_after_window)


class SubscriptionViewsetTenantIsolationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.org_a = Organization.objects.create(
            name="Org A",
            slug="org-a-test",
            contact_email="orga@test.com",
            contact_phone="0000000001",
            code="A001",
        )
        self.org_b = Organization.objects.create(
            name="Org B",
            slug="org-b-test",
            contact_email="orgb@test.com",
            contact_phone="0000000002",
            code="B002",
        )
        self.exec_user = User.objects.create_user(
            username="exec_a",
            email="exec_a@test.com",
            password="password123",
            organization=self.org_a,
            role="admin",
        )
        self.member_user = User.objects.create_user(
            username="member_a",
            email="member_a@test.com",
            password="password123",
            organization=self.org_a,
            role="member",
        )

        self.sub_a = Subscription.objects.create(
            name="Sub A",
            description="A",
            amount=50,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            organization=self.org_a,
            assignees_category="EXECUTIVES",
            is_active=True,
        )
        self.sub_b = Subscription.objects.create(
            name="Sub B",
            description="B",
            amount=60,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            organization=self.org_b,
            assignees_category="BOTH",
            is_active=True,
        )

    def _build_viewset(self, user):
        request = self.factory.get('/api/v1/subscriptions')
        request.user = user
        view = SubscriptionViewSet()
        view.request = request
        return view

    def test_executive_queryset_is_scoped_to_organization(self):
        queryset = self._build_viewset(self.exec_user).get_queryset()
        self.assertEqual(list(queryset), [self.sub_a])

    def test_member_queryset_only_returns_assigned_subscriptions_in_org(self):
        queryset = self._build_viewset(self.member_user).get_queryset()
        self.assertEqual(list(queryset), [])

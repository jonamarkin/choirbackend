from django.test import TestCase
from django.contrib.auth import get_user_model
from datetime import date, timedelta
from core.models import Organization
from subscriptions.models import Subscription, UserSubscription

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

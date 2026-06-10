from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.test.client import RequestFactory
from datetime import date, timedelta
from rest_framework.test import APIRequestFactory, force_authenticate

from core.models import Organization
from subscriptions.models import DirectDebit, Subscription, UserSubscription, PaymentTransaction
from subscriptions.serializers.direct_debit_serializers import (
    DirectDebitUpdateSerializer,
    RegisterDirectDebitRequestSerializer,
)
from subscriptions.services.hubtel_service import HubtelPaymentService
from subscriptions.views.direct_debit_views import DirectDebitViewSet
from subscriptions.views.subscription_views import SubscriptionViewSet
from wallet.models import MobileWallet

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


class DirectDebitImplementationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Direct Debit Org",
            slug="direct-debit-org",
            contact_email="dd@test.com",
            contact_phone="0000000003",
            code="D001",
        )
        self.user = User.objects.create_user(
            username="dd_user",
            email="dd@test.com",
            password="password123",
            organization=self.organization,
            role="member",
        )
        self.subscription = Subscription.objects.create(
            name="Direct Debit Subscription",
            description="Direct debit checks",
            amount=Decimal("100.00"),
            start_date=date.today() - timedelta(days=1),
            end_date=date.today() + timedelta(days=30),
            organization=self.organization,
            assignees_category="BOTH",
            is_active=True,
        )
        self.user_subscription = UserSubscription.objects.get(
            user=self.user,
            subscription=self.subscription,
        )
        self.wallet = MobileWallet.objects.create(
            name="Primary wallet",
            user=self.user,
            network="MTN",
            account_number="233201234567",
            is_active=True,
            verified_at=timezone.now(),
        )

    def _direct_debit(self, **overrides):
        attrs = {
            "user": self.user,
            "wallet": self.wallet,
            "amount": Decimal("20.00"),
            "period_type": "MONTHLY",
            "user_subscription": self.user_subscription,
            "next_payment_date": date.today(),
            "hubtel_preapproval_id": "hubtel-preapproval-1",
            "initiate_client_reference": "init-ref-1",
            "approval_status": True,
            "is_active": True,
        }
        attrs.update(overrides)
        return DirectDebit.objects.create(**attrs)

    @override_settings(DEBUG=False, HUBTEL_CONFIG={"WHITELISTED_IPS": []})
    def test_empty_webhook_whitelist_rejects_outside_debug(self):
        request = RequestFactory().post("/webhook", {}, REMOTE_ADDR="127.0.0.1")
        self.assertFalse(HubtelPaymentService().validate_callback_ip(request))

    @override_settings(DEBUG=True, HUBTEL_CONFIG={"WHITELISTED_IPS": []})
    def test_empty_webhook_whitelist_allows_debug(self):
        request = RequestFactory().post("/webhook", {}, REMOTE_ADDR="127.0.0.1")
        self.assertTrue(HubtelPaymentService().validate_callback_ip(request))

    @override_settings(DEBUG=False, HUBTEL_CONFIG={"WHITELISTED_IPS": ["10.0.0.1"]})
    def test_webhook_whitelist_validates_request_ip(self):
        allowed = RequestFactory().post("/webhook", {}, REMOTE_ADDR="10.0.0.1")
        rejected = RequestFactory().post("/webhook", {}, REMOTE_ADDR="10.0.0.2")

        service = HubtelPaymentService()
        self.assertTrue(service.validate_callback_ip(allowed))
        self.assertFalse(service.validate_callback_ip(rejected))

    @patch("core.services.email_service.EmailService.send_payment_success_email")
    def test_success_callback_replay_does_not_double_credit(self, send_email):
        direct_debit = self._direct_debit()
        transaction = PaymentTransaction.objects.create(
            user_subscription=self.user_subscription,
            user=self.user,
            organization=self.organization,
            direct_debit=direct_debit,
            client_reference="dd-success-ref",
            amount=Decimal("20.00"),
            description="Direct debit",
            status="pending",
        )
        callback = {
            "ResponseCode": "0000",
            "Data": {
                "ClientReference": transaction.client_reference,
                "TransactionId": "hubtel-tx-1",
                "ExternalTransactionId": "external-1",
                "Charges": "1.00",
                "AmountAfterCharges": "19.00",
            },
        }

        service = HubtelPaymentService()
        first_success, _, _ = service.handle_direct_debit_charge_callback(callback)
        second_callback = {**callback, "Data": {**callback["Data"], "Charges": "2.00"}}
        second_success, second_message, _ = service.handle_direct_debit_charge_callback(second_callback)

        self.user_subscription.refresh_from_db()
        direct_debit.refresh_from_db()
        self.assertTrue(first_success)
        self.assertTrue(second_success)
        self.assertEqual(second_message, "Callback already processed")
        self.assertEqual(self.user_subscription.amount_paid, Decimal("20.00"))
        self.assertEqual(direct_debit.consecutive_failed_charges, 0)
        self.assertEqual(send_email.call_count, 1)

    def test_failed_callback_replay_does_not_double_count_failure(self):
        direct_debit = self._direct_debit()
        transaction = PaymentTransaction.objects.create(
            user_subscription=self.user_subscription,
            user=self.user,
            organization=self.organization,
            direct_debit=direct_debit,
            client_reference="dd-failed-ref",
            amount=Decimal("20.00"),
            description="Direct debit",
            status="pending",
        )
        callback = {
            "ResponseCode": "2001",
            "Data": {
                "ClientReference": transaction.client_reference,
                "Description": "Insufficient funds",
            },
        }

        service = HubtelPaymentService()
        service.handle_direct_debit_charge_callback(callback)
        service.handle_direct_debit_charge_callback(callback)

        direct_debit.refresh_from_db()
        self.assertEqual(direct_debit.consecutive_failed_charges, 1)

    def test_charge_direct_debit_rejects_existing_inflight_charge(self):
        direct_debit = self._direct_debit()
        PaymentTransaction.objects.create(
            user_subscription=self.user_subscription,
            user=self.user,
            organization=self.organization,
            direct_debit=direct_debit,
            client_reference="dd-inflight-ref",
            amount=Decimal("20.00"),
            description="Direct debit",
            status="pending",
        )

        with self.assertRaisesMessage(ValueError, "already in progress"):
            HubtelPaymentService().charge_direct_debit(direct_debit)

    def test_direct_debit_amount_must_be_positive(self):
        with self.assertRaisesMessage(Exception, "Amount must be greater than zero"):
            self._direct_debit(amount=Decimal("0.00"))

        update_serializer = DirectDebitUpdateSerializer(data={"amount": "0.00"})
        self.assertFalse(update_serializer.is_valid())
        self.assertIn("amount", update_serializer.errors)

        request = RequestFactory().post("/direct-debits/register")
        request.user = self.user
        register_serializer = RegisterDirectDebitRequestSerializer(
            data={
                "subscription_id": str(self.subscription.id),
                "wallet_id": str(self.wallet.id),
                "amount": "-1.00",
                "period_type": "MONTHLY",
            },
            context={"request": request},
        )
        self.assertFalse(register_serializer.is_valid())
        self.assertIn("amount", register_serializer.errors)

    def test_destroy_soft_deactivates_direct_debit(self):
        direct_debit = self._direct_debit()
        request = APIRequestFactory().delete(f"/direct-debits/{direct_debit.id}")
        force_authenticate(request, user=self.user)
        response = DirectDebitViewSet.as_view({"delete": "destroy"})(
            request, pk=direct_debit.id
        )

        direct_debit.refresh_from_db()
        self.assertEqual(response.status_code, 204)
        self.assertFalse(direct_debit.is_active)
        self.assertTrue(DirectDebit.objects.filter(id=direct_debit.id).exists())

    def test_fully_paid_subscription_deactivates_mandate(self):
        direct_debit = self._direct_debit()
        self.user_subscription.amount_paid = self.subscription.amount
        self.user_subscription.status = "fully_paid"
        self.user_subscription.save(update_fields=["amount_paid", "status"])

        with self.assertRaisesMessage(ValueError, "already fully paid"):
            HubtelPaymentService().charge_direct_debit(direct_debit)

        direct_debit.refresh_from_db()
        self.assertFalse(direct_debit.is_active)

    def test_preapproval_callback_rejects_mismatched_identifiers(self):
        direct_debit = self._direct_debit()
        service = HubtelPaymentService()

        success, message, _ = service.handle_direct_debit_preapproval_callback({
            "ClientReferenceId": direct_debit.initiate_client_reference,
            "PreapprovalStatus": "APPROVED",
            "HubtelPreapprovalId": "different-id",
            "CustomerMsisdn": self.wallet.account_number,
        })
        self.assertFalse(success)
        self.assertEqual(message, "HubtelPreapprovalId mismatch")

        success, message, _ = service.handle_direct_debit_preapproval_callback({
            "ClientReferenceId": direct_debit.initiate_client_reference,
            "PreapprovalStatus": "APPROVED",
            "HubtelPreapprovalId": direct_debit.hubtel_preapproval_id,
            "CustomerMsisdn": "233209999999",
        })
        self.assertFalse(success)
        self.assertEqual(message, "CustomerMsisdn mismatch")

    def test_preapproval_callback_with_matching_identifiers_approves(self):
        direct_debit = self._direct_debit(approval_status=False)

        success, message, _ = HubtelPaymentService().handle_direct_debit_preapproval_callback({
            "ClientReferenceId": direct_debit.initiate_client_reference,
            "PreapprovalStatus": "APPROVED",
            "HubtelPreapprovalId": direct_debit.hubtel_preapproval_id,
            "CustomerMsisdn": self.wallet.account_number,
        })

        direct_debit.refresh_from_db()
        self.assertTrue(success)
        self.assertEqual(message, "Preapproval approved")
        self.assertTrue(direct_debit.approval_status)

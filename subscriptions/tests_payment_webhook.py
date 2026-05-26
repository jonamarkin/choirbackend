"""
Tests for the Hubtel payment webhook hardening.

Covers: source-IP allowlist, amount + status reconciliation against
Hubtel's status API, atomic + select_for_update race-safety,
always-200 ack behavior for parseable rejections, and the on_commit
email decoupling.
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Organization
from subscriptions.models import (
    PaymentTransaction,
    Subscription,
    UserSubscription,
)
from subscriptions.services.hubtel_service import HubtelPaymentService

User = get_user_model()

WEBHOOK_URL = '/api/v1/subscriptions/payments/webhook'

DEFAULT_HUBTEL_CONFIG = {
    'API_ID': 'test_id',
    'API_KEY': 'test_key',
    'MERCHANT_ACCOUNT_NUMBER': '12345',
    'PAYMENT_API_URL': 'https://example.test/init',
    'STATUS_API_URL': 'https://example.test/status',
    'CALLBACK_URL': 'https://example.test/callback',
    'RETURN_URL': 'https://example.test/return',
    'CANCELLATION_URL': 'https://example.test/cancel',
    # APIClient defaults REMOTE_ADDR=127.0.0.1, so this allows webhook traffic
    # from the test client by default.
    'WHITELISTED_IPS': ['127.0.0.1'],
    'PAYMENT_EXPIRY_MINUTES': 5,
    'SMS_CLIENT_ID': '',
    'SMS_CLIENT_SECRET': '',
    'SMS_SENDER_ID': '',
    'SMS_BASE_URL': '',
}


def _make_hubtel_status_response(*, status_value='Paid', amount=100, client_reference='ref'):
    return {
        'responseCode': '0000',
        'data': {
            'status': status_value,
            'amount': float(amount),
            'clientReference': client_reference,
            'transactionId': 'hubtel-txn-1',
            'externalTransactionId': 'ext-1',
            'paymentMethod': 'mobilemoney',
            'charges': 0,
            'amountAfterCharges': float(amount),
        },
    }


def _make_callback_payload(*, client_reference='ref', amount=100, status_value='Success', response_code='0000'):
    return {
        'ResponseCode': response_code,
        'Status': status_value,
        'Data': {
            'ClientReference': client_reference,
            'Status': status_value,
            'Amount': amount,
            'Description': 'Test payment',
            'PaymentDetails': {
                'Channel': 'mtn-gh',
                'PaymentType': 'mobilemoney',
                'MobileMoneyNumber': '0241234567',
            },
            'SalesInvoiceId': 'inv-1',
        },
    }


def _hubtel_get_mock(*, response_json=None, raise_exc=None):
    response = MagicMock()
    if raise_exc is not None:
        response.raise_for_status.side_effect = raise_exc
    else:
        response.raise_for_status.return_value = None
    response.json.return_value = response_json or {}
    return patch(
        'subscriptions.services.hubtel_service.requests.get',
        return_value=response,
    )


@override_settings(HUBTEL_CONFIG=DEFAULT_HUBTEL_CONFIG, DEBUG=False)
class HubtelWebhookTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='WebhookOrg', code='WHK')
        self.user = User.objects.create_user(
            username='wh_user',
            email='wh@test.com',
            password='pass1234',
            organization=self.org,
            role='member',
        )
        self.subscription = Subscription.objects.create(
            name='Annual Dues',
            description='X',
            amount=Decimal('100'),
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            organization=self.org,
            assignees_category='BOTH',
            is_active=True,
        )
        self.user_subscription = UserSubscription.objects.get(
            user=self.user, subscription=self.subscription,
        )
        self.transaction = PaymentTransaction.objects.create(
            user_subscription=self.user_subscription,
            user=self.user,
            organization=self.org,
            client_reference='ref-success',
            amount=Decimal('100'),
            description='Test',
            status='initiated',
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        email_patcher = patch('core.services.email_service.EmailService.send_payment_success_email')
        self.mock_email = email_patcher.start()
        self.addCleanup(email_patcher.stop)

    def _post_callback(self, payload):
        return self.client.post(WEBHOOK_URL, payload, format='json')

    def test_happy_path(self):
        with _hubtel_get_mock(
            response_json=_make_hubtel_status_response(amount=100, client_reference='ref-success')
        ), self.captureOnCommitCallbacks(execute=True):
            response = self._post_callback(
                _make_callback_payload(client_reference='ref-success', amount=100)
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'success')

        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, 'success')
        self.assertIsNotNone(self.transaction.confirmed_at)
        self.assertEqual(self.transaction.hubtel_transaction_id, 'hubtel-txn-1')

        self.user_subscription.refresh_from_db()
        self.assertEqual(self.user_subscription.amount_paid, Decimal('100'))
        self.mock_email.assert_called_once()

    def test_duplicate_callback_after_success(self):
        payload = _make_callback_payload(client_reference='ref-success', amount=100)
        with _hubtel_get_mock(
            response_json=_make_hubtel_status_response(amount=100, client_reference='ref-success')
        ), self.captureOnCommitCallbacks(execute=True):
            first = self._post_callback(payload)
            second = self._post_callback(payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data['status'], 'success')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data['status'], 'success')
        self.assertIn('Duplicate', second.data['message'])

        self.user_subscription.refresh_from_db()
        self.assertEqual(self.user_subscription.amount_paid, Decimal('100'))
        # Email fires exactly once (only the first call credits).
        self.assertEqual(self.mock_email.call_count, 1)

    def test_double_call_idempotent_direct_service(self):
        """
        Idempotency contract: calling handle_callback twice in sequence
        credits the user exactly once. True concurrent SELECT FOR UPDATE
        behavior is exercised only on Postgres in CI; this asserts the
        contract at the service layer.
        """
        svc = HubtelPaymentService()
        payload = _make_callback_payload(client_reference='ref-success', amount=100)
        with _hubtel_get_mock(
            response_json=_make_hubtel_status_response(amount=100, client_reference='ref-success')
        ), self.captureOnCommitCallbacks(execute=True):
            ok1, _msg1, _tx1 = svc.handle_callback(payload, request=None)
            ok2, msg2, _tx2 = svc.handle_callback(payload, request=None)

        self.assertTrue(ok1)
        self.assertTrue(ok2)
        self.assertIn('Duplicate', msg2)
        self.user_subscription.refresh_from_db()
        self.assertEqual(self.user_subscription.amount_paid, Decimal('100'))

    def test_amount_mismatch_rejected(self):
        # Hubtel status API reports a smaller amount than the transaction
        # expects — reconciliation should reject.
        with _hubtel_get_mock(
            response_json=_make_hubtel_status_response(amount=10, client_reference='ref-success')
        ), self.captureOnCommitCallbacks(execute=True):
            response = self._post_callback(
                _make_callback_payload(client_reference='ref-success', amount=100)
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'rejected')
        self.assertIn('amount mismatch', response.data['reason'])

        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, 'initiated')
        self.user_subscription.refresh_from_db()
        self.assertEqual(self.user_subscription.amount_paid, Decimal('0'))
        self.mock_email.assert_not_called()

    def test_status_api_says_unpaid(self):
        with _hubtel_get_mock(
            response_json=_make_hubtel_status_response(
                status_value='Unpaid', amount=100, client_reference='ref-success',
            )
        ), self.captureOnCommitCallbacks(execute=True):
            response = self._post_callback(
                _make_callback_payload(client_reference='ref-success', amount=100)
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'rejected')
        self.assertIn('status mismatch', response.data['reason'])

        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, 'initiated')
        self.mock_email.assert_not_called()

    def test_unknown_client_reference(self):
        with _hubtel_get_mock(
            response_json=_make_hubtel_status_response(amount=100, client_reference='nope')
        ):
            response = self._post_callback(
                _make_callback_payload(client_reference='nope', amount=100)
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'rejected')
        self.assertIn('Transaction not found', response.data['reason'])

    def test_schema_invalid_missing_data(self):
        response = self.client.post(
            WEBHOOK_URL,
            {'ResponseCode': '0000', 'Status': 'Success', 'Data': {}},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'rejected')
        self.assertEqual(response.data['reason'], 'schema_invalid')

    def test_status_api_unreachable_defers(self):
        with _hubtel_get_mock(
            raise_exc=requests.RequestException('connection refused')
        ), self.captureOnCommitCallbacks(execute=True):
            response = self._post_callback(
                _make_callback_payload(client_reference='ref-success', amount=100)
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'rejected')
        self.assertIn('Status check failed', response.data['reason'])

        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, 'initiated')
        self.mock_email.assert_not_called()

    def test_email_failure_does_not_revert_success(self):
        """
        on_commit fires after the inner atomic block has committed; an
        SMTP failure must not undo the success state.
        """
        self.mock_email.side_effect = RuntimeError('SMTP boom')
        with _hubtel_get_mock(
            response_json=_make_hubtel_status_response(amount=100, client_reference='ref-success')
        ):
            try:
                with self.captureOnCommitCallbacks(execute=True):
                    response = self._post_callback(
                        _make_callback_payload(client_reference='ref-success', amount=100)
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.data['status'], 'success')
            except RuntimeError:
                # captureOnCommitCallbacks re-raises exceptions from on_commit
                # callbacks; DB state has already been committed by that point.
                pass

        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, 'success')
        self.user_subscription.refresh_from_db()
        self.assertEqual(self.user_subscription.amount_paid, Decimal('100'))


@override_settings(DEBUG=False)
class HubtelIPAllowlistTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='IPOrg', code='IP1')
        self.user = User.objects.create_user(
            username='ip_user', email='ip@test.com', password='pass1234',
            organization=self.org, role='member',
        )
        self.subscription = Subscription.objects.create(
            name='Sub IP', description='x', amount=Decimal('50'),
            start_date=date.today(), end_date=date.today() + timedelta(days=30),
            organization=self.org, assignees_category='BOTH', is_active=True,
        )
        self.user_subscription = UserSubscription.objects.get(
            user=self.user, subscription=self.subscription,
        )
        self.transaction = PaymentTransaction.objects.create(
            user_subscription=self.user_subscription,
            user=self.user,
            organization=self.org,
            client_reference='ip-ref',
            amount=Decimal('50'),
            description='x',
            status='initiated',
        )

    def test_request_from_non_allowlisted_ip_rejected(self):
        with self.settings(
            HUBTEL_CONFIG={**DEFAULT_HUBTEL_CONFIG, 'WHITELISTED_IPS': ['10.0.0.1']},
        ):
            response = self.client.post(
                WEBHOOK_URL,
                _make_callback_payload(client_reference='ip-ref', amount=50),
                format='json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'rejected')
        self.assertIn('Source IP not allowed', response.data['reason'])

        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, 'initiated')

    def test_empty_allowlist_with_debug_false_rejects(self):
        with self.settings(
            HUBTEL_CONFIG={**DEFAULT_HUBTEL_CONFIG, 'WHITELISTED_IPS': []},
        ):
            response = self.client.post(
                WEBHOOK_URL,
                _make_callback_payload(client_reference='ip-ref', amount=50),
                format='json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'rejected')
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, 'initiated')

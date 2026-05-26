"""
Hubtel Payment Service
Handles all interactions with the Hubtel Online Checkout API.
"""
import base64
import hashlib
import json
import logging
import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone

from subscriptions.models import PaymentTransaction

logger = logging.getLogger(__name__)


class HubtelPaymentService:
    """
    Service for interacting with Hubtel Payment API.
    Handles payment initiation, status checks, and webhooks.
    """

    def __init__(self):
        self.config = settings.HUBTEL_CONFIG

    def get_auth_header(self):
        """Generate Basic Auth header for Hubtel API"""
        api_id = self.config['API_ID']
        api_key = self.config['API_KEY']
        credentials = f"{api_id}:{api_key}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def initiate_payment(self, user_subscription, amount=None, metadata=None, return_url=None, cancellation_url=None):
        """
        Initiate payment with Hubtel.

        Args:
            user_subscription: UserSubscription instance
            amount: Payment amount (defaults to outstanding amount)
            metadata: Additional metadata dict
            return_url: Custom return URL for mobile deep linking (optional)
            cancellation_url: Custom cancellation URL for mobile deep linking (optional)

        Returns:
            PaymentTransaction object

        Raises:
            ValueError: If validation fails
            requests.RequestException: If API call fails
        """
        from subscriptions.models import PaymentTransaction

        # Validate that payment can be made
        can_pay, message = user_subscription.can_make_payment()
        if not can_pay:
            raise ValueError(message)

        # Calculate amount
        if amount is None:
            amount = user_subscription.get_outstanding_amount()
        else:
            amount = Decimal(str(amount))

        # Validate amount
        if amount <= 0:
            raise ValueError("Payment amount must be greater than zero")

        outstanding = user_subscription.get_outstanding_amount()
        if amount > outstanding:
            raise ValueError(
                f"Payment amount ({amount}) cannot exceed outstanding amount ({outstanding})"
            )

        # Generate unique client reference (max 32 characters)
        client_reference = self.generate_client_reference(user_subscription)

        # Create payment transaction record
        transaction = PaymentTransaction.objects.create(
            user_subscription=user_subscription,
            user=user_subscription.user,
            organization=user_subscription.subscription.organization,
            client_reference=client_reference,
            amount=amount,
            description=f"{user_subscription.subscription.name} - Payment",
            status='initiated',
            expires_at=timezone.now() + timedelta(minutes=self.config['PAYMENT_EXPIRY_MINUTES']),
            metadata=metadata or {}
        )

        # Prepare Hubtel API request
        # Use client-provided URLs for mobile deep links, or fall back to config defaults
        payload = {
            "totalAmount": float(amount),
            "description": transaction.description,
            "callbackUrl": self.config['CALLBACK_URL'],
            "returnUrl": return_url or self.config['RETURN_URL'],
            "merchantAccountNumber": self.config['MERCHANT_ACCOUNT_NUMBER'],
            "cancellationUrl": cancellation_url or self.config['CANCELLATION_URL'],
            "clientReference": client_reference,
        }

        # Add optional payee information
        if user_subscription.user.first_name and user_subscription.user.last_name:
            payload["payeeName"] = f"{user_subscription.user.first_name} {user_subscription.user.last_name}"

        if user_subscription.user.phone_number:
            payload["payeeMobileNumber"] = user_subscription.user.phone_number

        if user_subscription.user.email:
            payload["payeeEmail"] = user_subscription.user.email

        # Make API request to Hubtel
        try:
            response = requests.post(
                self.config['PAYMENT_API_URL'],
                json=payload,
                headers={
                    'Authorization': self.get_auth_header(),
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                timeout=30
            )
            response.raise_for_status()

            response_data = response.json()
            logger.debug(f"Hubtel initiate response for {client_reference}: {response_data}")

            # Check if request was successful
            if response_data.get('responseCode') == '0000':
                data = response_data.get('data', {})
                transaction.checkout_id = data.get('checkoutId', '')
                transaction.checkout_url = data.get('checkoutUrl', '')
                transaction.save()

                return transaction
            else:
                # Payment initiation failed
                error_message = response_data.get('message', 'Unknown error from Hubtel')
                transaction.status = 'failed'
                transaction.error_message = error_message
                transaction.save()
                raise ValueError(f"Hubtel payment initiation failed: {error_message}")

        except requests.RequestException as e:
            # Network or HTTP error
            transaction.status = 'failed'
            transaction.error_message = str(e)
            transaction.save()
            raise

    def handle_callback(self, callback_data, request=None):
        """
        Process Hubtel payment callback inside an atomic block with row-level
        locking on the PaymentTransaction. Reconciles the callback against
        Hubtel's status API before mutating local state.

        Args:
            callback_data: Dict containing callback data from Hubtel
            request: Optional Django request object for IP validation

        Returns:
            Tuple (success: bool, message: str, transaction: PaymentTransaction or None)
        """
        # Authenticate source — IP allowlist
        if request is not None and not self.validate_callback_ip(request):
            return False, "Source IP not allowed", None

        # Extract client reference up-front (used for lookup and logging)
        client_reference = callback_data.get('Data', {}).get('ClientReference')
        if not client_reference:
            return False, "Missing ClientReference in callback", None

        response_code = callback_data.get('ResponseCode')
        outer_status = callback_data.get('Status')
        data = callback_data.get('Data', {}) or {}
        inner_status = data.get('Status')

        try:
            with db_transaction.atomic():
                try:
                    transaction = (
                        PaymentTransaction.objects
                        .select_for_update()
                        .get(client_reference=client_reference)
                    )
                except PaymentTransaction.DoesNotExist:
                    return False, f"Transaction not found: {client_reference}", None

                # Already terminal — apply dedupe hash check under the lock
                if transaction.status in ('success', 'failed', 'refunded'):
                    if self.is_duplicate_callback(transaction, callback_data):
                        return True, "Duplicate callback (already processed)", transaction
                    logger.warning(
                        f"Callback for {client_reference} arrived after terminal status "
                        f"'{transaction.status}'; not re-processing"
                    )
                    return True, "Already in terminal state", transaction

                # Callback itself signals failure — mark failed and stop
                callback_signals_success = (
                    response_code == '0000'
                    and outer_status == 'Success'
                    and inner_status == 'Success'
                )
                if not callback_signals_success:
                    error_message = data.get('Description', 'Payment failed')
                    transaction.mark_as_failed(error_message, callback_data)
                    return False, error_message, transaction

                # Reconcile against Hubtel's authoritative status API before
                # mutating local success state.
                try:
                    hubtel_data = self._fetch_status(client_reference)
                except (requests.RequestException, ValueError) as e:
                    logger.error(
                        f"Hubtel status check failed for {client_reference}: {e}",
                        exc_info=True,
                    )
                    return False, "Status check failed; deferring", transaction

                hubtel_payment_status = hubtel_data.get('status')
                try:
                    hubtel_amount = Decimal(str(hubtel_data.get('amount', 0)))
                except (TypeError, InvalidOperation):
                    hubtel_amount = Decimal('0')
                hubtel_ref = hubtel_data.get('clientReference')

                if hubtel_payment_status != 'Paid':
                    logger.error(
                        f"Reconciliation rejected for {client_reference}: "
                        f"Hubtel status={hubtel_payment_status!r}"
                    )
                    return False, "Reconciliation failed: status mismatch", transaction

                if hubtel_amount != transaction.amount:
                    logger.error(
                        f"Reconciliation rejected for {client_reference}: "
                        f"expected amount {transaction.amount}, Hubtel reported {hubtel_amount}"
                    )
                    return False, "Reconciliation failed: amount mismatch", transaction

                if hubtel_ref and hubtel_ref != transaction.client_reference:
                    logger.error(
                        f"Reconciliation rejected: clientReference mismatch "
                        f"expected={transaction.client_reference} got={hubtel_ref}"
                    )
                    return False, "Reconciliation failed: reference mismatch", transaction

                # Apply Hubtel-authoritative fields then mark success.
                transaction.hubtel_transaction_id = hubtel_data.get('transactionId', '') or ''
                transaction.network_transaction_id = hubtel_data.get('externalTransactionId', '') or ''
                transaction.payment_type = hubtel_data.get('paymentMethod', '') or transaction.payment_type
                transaction.charges = Decimal(str(hubtel_data.get('charges', 0) or 0))
                transaction.amount_after_charges = Decimal(str(hubtel_data.get('amountAfterCharges', 0) or 0))
                transaction.mark_as_success(callback_data)

                return True, "Payment processed successfully", transaction

        except (requests.RequestException, ValueError) as e:
            logger.error(f"Callback processing error for {client_reference}: {e}", exc_info=True)
            return False, f"Error processing callback: {e}", None

    def _fetch_status(self, client_reference):
        """
        Query Hubtel's status API for the given client_reference and return
        the parsed `data` dict from the response. Pure: does not mutate any
        local state.

        Raises:
            requests.RequestException on network/HTTP failure.
            ValueError if Hubtel responds with a non-success responseCode.
        """
        pos_sales_id = self.config['MERCHANT_ACCOUNT_NUMBER']
        url = f"{self.config['STATUS_API_URL']}/{pos_sales_id}/status"
        params = {'clientReference': client_reference}

        response = requests.get(
            url,
            params=params,
            headers={
                'Authorization': self.get_auth_header(),
                'Accept': 'application/json',
            },
            timeout=30,
        )
        response.raise_for_status()

        response_data = response.json()
        logger.debug(f"Hubtel status check response for {client_reference}: {response_data}")

        if response_data.get('responseCode') != '0000':
            raise ValueError(
                f"Hubtel status check non-success responseCode: {response_data.get('responseCode')}"
            )

        return response_data.get('data', {}) or {}

    def check_payment_status(self, transaction):
        """
        Query Hubtel API for payment status and apply updates to local
        state based on the response.

        Args:
            transaction: PaymentTransaction instance

        Returns:
            Updated PaymentTransaction object

        Raises:
            requests.RequestException: If API call fails
        """
        data = self._fetch_status(transaction.client_reference)
        payment_status = data.get('status')  # 'Paid', 'Unpaid', 'Refunded'

        if payment_status == 'Paid':
            transaction.hubtel_transaction_id = data.get('transactionId', '') or ''
            transaction.network_transaction_id = data.get('externalTransactionId', '') or ''
            transaction.payment_type = data.get('paymentMethod', '') or transaction.payment_type
            transaction.charges = Decimal(str(data.get('charges', 0) or 0))
            transaction.amount_after_charges = Decimal(str(data.get('amountAfterCharges', 0) or 0))

            if transaction.status != 'success':
                synthetic_callback = {'Data': data, 'ResponseCode': '0000', 'Status': 'Success'}
                transaction.mark_as_success(synthetic_callback)
            else:
                transaction.save()

        elif payment_status == 'Unpaid':
            transaction.status = 'pending'
            transaction.save()

        elif payment_status == 'Refunded':
            transaction.status = 'refunded'
            transaction.save()

        return transaction

    def generate_client_reference(self, user_subscription):
        """
        Generate unique client reference for transaction.
        Format: First 26 chars of UUID (to fit within 32 char limit with possible prefix)
        """
        reference = str(uuid.uuid4()).replace('-', '')[:26]
        # Ensure uniqueness
        while PaymentTransaction.objects.filter(client_reference=reference).exists():
            reference = str(uuid.uuid4()).replace('-', '')[:26]
        return reference

    def validate_callback_ip(self, request):
        """
        Validate that the callback originated from a whitelisted Hubtel IP.

        Fail-closed: when WHITELISTED_IPS is non-empty, only those IPs are
        allowed. When the allowlist is empty, fail open only if settings.DEBUG
        is True; otherwise reject and log.
        """
        whitelisted_ips = self.config.get('WHITELISTED_IPS', [])

        if not whitelisted_ips:
            if settings.DEBUG:
                logger.warning(
                    "Hubtel webhook IP allowlist not configured; allowing because DEBUG=True"
                )
                return True
            logger.warning(
                "Hubtel webhook IP allowlist not configured; rejecting in non-DEBUG mode"
            )
            return False

        # HTTP_X_FORWARDED_FOR is set by our reverse proxy (nginx → gunicorn);
        # the leftmost entry is the original client IP. This is only safe
        # because the request must traverse our trusted proxy before reaching
        # this code path.
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')

        if ip in whitelisted_ips:
            return True

        logger.warning(f"Hubtel webhook rejected: source IP {ip!r} not in allowlist")
        return False

    def is_duplicate_callback(self, transaction, callback_data):
        """
        Check if this exact callback payload has already been processed for
        a transaction that is already in a terminal state. Uses SHA-256 hash
        comparison on the canonicalised JSON.
        """
        if transaction.status in ('success', 'failed', 'refunded'):
            callback_hash = hashlib.sha256(
                json.dumps(callback_data, sort_keys=True).encode()
            ).hexdigest()

            if transaction.callback_data:
                existing_hash = hashlib.sha256(
                    json.dumps(transaction.callback_data, sort_keys=True).encode()
                ).hexdigest()

                if callback_hash == existing_hash:
                    return True

        return False

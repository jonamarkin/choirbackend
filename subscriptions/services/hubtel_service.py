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
from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.utils import timezone

from subscriptions.models import PaymentTransaction, UserSubscription, DirectDebit
from wallet.models import MobileWallet
from wallet.utils.wallet_network_type import WalletNetworkType

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

    def _process_callback(self, callback_data, *, succeeded, error_message, extra_fields=None):
        """
        Shared callback core: locate the transaction by ClientReference, de-dupe, then
        transition its state. Provider-specific handlers parse the payload (success predicate
        and field mapping) and delegate here so the common flow lives in one place.

        Returns:
            Tuple (success: bool, message: str, transaction: PaymentTransaction or None)
        """
        try:
            client_reference = callback_data.get('Data', {}).get('ClientReference')
            if not client_reference:
                return False, "Missing ClientReference in callback", None

            with transaction.atomic():
                try:
                    payment_transaction = PaymentTransaction.objects.select_for_update().get(
                        client_reference=client_reference
                    )
                except PaymentTransaction.DoesNotExist:
                    return False, f"Transaction not found: {client_reference}", None

                if payment_transaction.status in ['success', 'failed', 'expired', 'cancelled', 'refunded']:
                    return True, "Callback already processed", payment_transaction

                # Apply any provider-specific fields parsed from the callback.
                for field, value in (extra_fields or {}).items():
                    setattr(payment_transaction, field, value)

                if succeeded:
                    payment_transaction.mark_as_success(callback_data)
                    return True, "Payment processed successfully", payment_transaction

                payment_transaction.mark_as_failed(error_message, callback_data)
                return False, error_message, payment_transaction

        response_data = response.json()
        logger.debug(f"Hubtel status check response for {client_reference}: {response_data}")

        if response_data.get('responseCode') != '0000':
            raise ValueError(
                f"Hubtel status check non-success responseCode: {response_data.get('responseCode')}"
            )

        return response_data.get('data', {}) or {}

    def handle_callback(self, callback_data, request=None):
        """
        Process a Hubtel Online Checkout payment callback.

        Args:
            callback_data: Dict containing callback data from Hubtel
            request: Optional Django request object for IP validation

        Returns:
            Tuple (success: bool, message: str, transaction: PaymentTransaction or None)
        """
        # Validate IP address if request provided
        # if request and not self.validate_callback_ip(request):
        #     return False, "Invalid IP address", None

        data = callback_data.get('Data', {})
        succeeded = (
            callback_data.get('ResponseCode') == '0000'
            and callback_data.get('Status') == 'Success'
            and data.get('Status') == 'Success'
        )
        result = self._process_callback(
            callback_data,
            succeeded=succeeded,
            error_message=data.get('Description', 'Payment failed'),
        )

        # Checkout-specific enrichment: pull extra fields from the status API (non-blocking).
        success, _, transaction = result
        if success and transaction and transaction.status == 'success':
            try:
                self.check_payment_status(transaction)
            except Exception as e:
                logger.warning(f"Status check failed after callback success: {e}")

        return result

    def handle_direct_debit_charge_callback(self, callback_data):
        """
        Process the asynchronous callback for a direct-debit charge.

        Unlike the checkout callback, success is determined solely by ResponseCode == '0000'
        ('2001' = failed); the payload has no top-level Status and carries flat Data fields.

        Returns:
            Tuple (success: bool, message: str, transaction: PaymentTransaction or None)
        """
        data = callback_data.get('Data', {})
        succeeded = callback_data.get('ResponseCode') == '0000'
        extra_fields = {
            'hubtel_transaction_id': data.get('TransactionId', ''),
            'network_transaction_id': data.get('ExternalTransactionId', ''),
            'charges': Decimal(str(data.get('Charges', 0))),
            'amount_after_charges': Decimal(str(data.get('AmountAfterCharges', 0))),
        }
        return self._process_callback(
            callback_data,
            succeeded=succeeded,
            error_message=data.get('Description', 'Direct debit charge failed'),
            extra_fields=extra_fields,
        )

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
                return True
            logger.error("Hubtel callback rejected: HUBTEL_WHITELISTED_IPS is not configured.")
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

    @staticmethod
    def get_direct_debit_channel(wallet: MobileWallet):
        if wallet.network == WalletNetworkType.MTN.value:
            return "mtn-gh-direct-debit"
        elif wallet.network == WalletNetworkType.TELECEL.value:
            return "vodafone-gh-direct-debit"
        else:
            raise ValueError(f"Unsupported wallet network: {wallet.network}")

    def initiate_hubtel_direct_debit_registration(self, wallet_id, user_subscription_id,
                                                  amount, period_type):
        """
        Initiates the Hubtel direct debit registration process for a specific wallet and user subscription.

        This method registers a direct debit mandate with Hubtel for automated periodic payments, ensuring
        pre-validation is completed locally to avoid creating inconsistent states on the remote system.

        Parameters:
            wallet_id (int): The ID of the mobile wallet to be linked to the direct debit.
            user_subscription_id (int): The ID of the user's subscription associated with the mandate.
            amount (float): The payment amount to be periodically collected.
            period_type (str): The frequency or duration type for the recurring debit.

        Returns:
            tuple: A tuple containing the created direct debit object and the verification type (if registration
                   succeeds), or a tuple of (None, None) if the attempt fails.
        """
        wallet = MobileWallet.objects.filter(id=wallet_id).first()
        user_subscription = UserSubscription.objects.filter(id=user_subscription_id).first()

        # Validate locally BEFORE registering a mandate at Hubtel, so we never
        # leave an orphaned remote mandate we cannot persist.
        if wallet.user_id != user_subscription.user_id:
            raise ValueError("Wallet does not belong to the subscription's user.")
        if not wallet.is_active or wallet.verified_at is None:
            raise ValueError("Wallet must be active and verified.")

        client_reference = self.generate_client_reference(user_subscription)
        client_account_number = wallet.account_number
        channel = self.get_direct_debit_channel(wallet)

        try:
            response = requests.post(
                self.config['DIRECT_DEBIT_REGISTRATION_URL'],
                json={
                    "clientReferenceId": client_reference,
                    "customerMsisdn": client_account_number,
                    "channel": channel,
                    "callbackUrl": self.config['DIRECT_DEBIT_REGISTER_CALLBACK_URL'],
                },
                headers={
                    'Authorization': self.get_auth_header(),
                    'Content-Type': 'application/json',
                },
                timeout=30
            )

            response.raise_for_status()
            response_data = response.json()
            logger.info("Hubtel direct debit registration response: %s", response_data)

            if response_data.get('responseCode') == '2000':
                data = response_data.get('data', {})
                verification_type = data.get('verificationType')

                direct_debit = DirectDebit.objects.create(
                    user=user_subscription.user,
                    wallet=wallet,
                    amount=amount,
                    period_type=period_type,
                    user_subscription=user_subscription,
                    hubtel_preapproval_id=data.get('hubtelPreApprovalId') or '',
                    initiate_client_reference=client_reference,
                    otp_prefix=data.get('otpPrefix') or '',
                )
                return direct_debit, verification_type
            else:
                return None, None
        except (requests.RequestException, ValidationError) as e:
            logger.warning("Failed to initiate Hubtel direct debit registration: %s", e)
            return None, None

    def verify_hubtel_direct_debit_otp(self, otp_code, direct_debit_id):
        direct_debit = DirectDebit.objects.filter(id=direct_debit_id).first()
        if not direct_debit:
            return False

        try:
            response = requests.post(
                self.config['DIRECT_DEBIT_OTP_VERIFY_URL'],
                json={
                    "customerMsisdn": direct_debit.wallet.account_number,
                    "hubtelPreApprovalId": direct_debit.hubtel_preapproval_id,
                    "clientReferenceId": direct_debit.initiate_client_reference,
                    "otp": f"{direct_debit.otp_prefix}-{otp_code}",
                },
                headers={
                    'Authorization': self.get_auth_header(),
                    'Content-Type': 'application/json',
                },
                timeout=30
            )
            response.raise_for_status()
            response_data = response.json()
            return response_data.get('responseCode') == '2000'
        except requests.RequestException as e:
            logger.warning("Failed to verify Hubtel direct debit OTP: %s", e)
            return False

    def check_hubtel_direct_debit_preapproval_status(self, direct_debit_id):
        direct_debit = DirectDebit.objects.filter(id=direct_debit_id).first()
        if not direct_debit:
            return None
        url = f"{self.config['DIRECT_DEBIT_PREAPPROVAL_STATUS_URL']}/{direct_debit.initiate_client_reference}/status"

        try:
            response = requests.get(
                url,
                headers={
                    'Authorization': self.get_auth_header(),
                    'Content-Type': 'application/json',
                },
                timeout=30
            )
            response.raise_for_status()
            response_data = response.json()
            data = response_data.get('data', {})
            if response_data.get('code') == '2000' and data.get('status') == 'APPROVED':
                direct_debit.mark_approved()
                return True
            else:
                return False

        except requests.RequestException as e:
            logger.warning("Failed to check Hubtel direct debit preapproval status: %s", e)
            return False

    def handle_direct_debit_preapproval_callback(self, callback_data):
        """
        Process Hubtel's asynchronous preapproval (registration) callback.

        Identifies the mandate by ClientReferenceId (DirectDebit.initiate_client_reference) and
        marks it approved when PreapprovalStatus == 'APPROVED'. Idempotent: a re-delivered
        APPROVED callback does not re-seed next_payment_date.

        Returns:
            Tuple (success: bool, message: str, direct_debit: DirectDebit or None)
        """
        client_reference = callback_data.get('ClientReferenceId')
        if not client_reference:
            return False, "Missing ClientReferenceId in callback", None

        direct_debit = DirectDebit.objects.filter(
            initiate_client_reference=client_reference
        ).first()
        if not direct_debit:
            return False, f"Direct debit not found: {client_reference}", None

        if callback_data.get('PreapprovalStatus') == 'APPROVED':
            hubtel_preapproval_id = callback_data.get('HubtelPreapprovalId')
            if hubtel_preapproval_id and hubtel_preapproval_id != direct_debit.hubtel_preapproval_id:
                logger.warning(
                    "Rejected preapproval callback for %s: HubtelPreapprovalId mismatch.",
                    direct_debit.id,
                )
                return False, "HubtelPreapprovalId mismatch", direct_debit

            customer_msisdn = callback_data.get('CustomerMsisdn')
            if customer_msisdn and customer_msisdn != direct_debit.wallet.account_number:
                logger.warning(
                    "Rejected preapproval callback for %s: CustomerMsisdn mismatch.",
                    direct_debit.id,
                )
                return False, "CustomerMsisdn mismatch", direct_debit

            if not direct_debit.approval_status:
                direct_debit.mark_approved()
            return True, "Preapproval approved", direct_debit

        return (
            False,
            f"Preapproval not approved: {callback_data.get('PreapprovalStatus')}",
            direct_debit,
        )

    def charge_direct_debit(self, direct_debit, metadata=None):
        """
        Charge an approved direct-debit mandate via Hubtel's Receive Money (RMP) endpoint.

        Mirrors initiate_payment: validate locally, create a PaymentTransaction, POST to Hubtel,
        then handle the response. The RMP endpoint is asynchronous — a ResponseCode of '0001'
        means the charge was accepted and is pending; the final state arrives on
        DIRECT_DEBIT_CHARGE_CALLBACK_URL (see handle_direct_debit_charge_callback).

        Args:
            direct_debit: DirectDebit instance (an approved, active mandate)
            metadata: Optional metadata dict stored on the PaymentTransaction

        Returns:
            PaymentTransaction (status 'pending' once Hubtel accepts the charge)

        Raises:
            ValueError: If validation fails or Hubtel rejects the charge
            requests.RequestException: If the API call fails
        """
        from subscriptions.models import PaymentTransaction

        terminal_skip_message = None
        with transaction.atomic():
            direct_debit = DirectDebit.objects.select_for_update().select_related(
                'wallet', 'user_subscription__subscription', 'user'
            ).get(pk=direct_debit.pk)

            # --- validation (analogues of initiate_payment's guards) ---
            if not direct_debit.is_active:
                raise ValueError("Direct debit is not active.")
            if not direct_debit.approval_status:
                raise ValueError("Direct debit mandate is not approved.")

            wallet = direct_debit.wallet
            # Charge-time wallet gate — the check deferred from DirectDebit.clean().
            if not wallet.is_active or wallet.verified_at is None:
                raise ValueError("Wallet must be active and verified.")

            user_subscription = direct_debit.user_subscription
            can_pay, message = user_subscription.can_make_payment()
            if not can_pay:
                if user_subscription.status in ['fully_paid', 'refunded']:
                    direct_debit.deactivate()
                    terminal_skip_message = message
                else:
                    raise ValueError(message)

            if terminal_skip_message is None:
                amount = Decimal(str(direct_debit.amount))
                if amount <= 0:
                    raise ValueError("Charge amount must be greater than zero.")
                outstanding = user_subscription.get_outstanding_amount()
                if amount > outstanding:
                    amount = outstanding  # never debit more than is owed (mirror initiate_payment cap)

                # Idempotency: don't start a second charge while one is in flight.
                if PaymentTransaction.objects.filter(
                    direct_debit=direct_debit, status__in=['initiated', 'pending']
                ).exists():
                    raise ValueError("A charge for this direct debit is already in progress.")

                client_reference = self.generate_client_reference(user_subscription)
                channel = self.get_direct_debit_channel(wallet)

                payment_transaction = PaymentTransaction.objects.create(
                    user_subscription=user_subscription,
                    user=direct_debit.user,
                    organization=user_subscription.subscription.organization,
                    direct_debit=direct_debit,
                    client_reference=client_reference,
                    amount=amount,
                    description=f"{user_subscription.subscription.name} - Direct Debit",
                    status='initiated',
                    metadata=metadata or {},
                )

        if terminal_skip_message is not None:
            raise ValueError(terminal_skip_message)

        payload = {
            # "CustomerName": f"{direct_debit.user.first_name} {direct_debit.user.last_name}".strip(),
            "CustomerMsisdn": wallet.account_number,
            # "CustomerEmail": direct_debit.user.email,
            "Channel": channel,
            "Amount": float(amount),
            "PrimaryCallbackUrl": self.config['DIRECT_DEBIT_CHARGE_CALLBACK_URL'],
            "Description": payment_transaction.description,
            "ClientReference": client_reference,
            # "HubtelPreApprovalId": direct_debit.hubtel_preapproval_id,
        }

        try:
            response = requests.post(
                self.config['DIRECT_DEBIT_PAYMENT_URL'],
                json=payload,
                headers={
                    'Authorization': self.get_auth_header(),
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                timeout=30
            )
            response.raise_for_status()
            response_data = response.json()
            logger.info("Hubtel direct debit charge response: %s", response_data)

            # '0001' = accepted & pending (final state via callback); '0000' if ever sync-success.
            if response_data.get('ResponseCode') in ('0001', '0000'):
                data = response_data.get('Data', {})
                payment_transaction.hubtel_transaction_id = data.get('TransactionId', '')
                payment_transaction.status = 'pending'
                payment_transaction.save(update_fields=['hubtel_transaction_id', 'status', 'updated_at'])
                return payment_transaction

            error_message = response_data.get('Message', 'Unknown error from Hubtel')
            payment_transaction.mark_as_failed(error_message, response_data)
            raise ValueError(f"Hubtel direct debit charge failed: {error_message}")

        except requests.RequestException as e:
            payment_transaction.mark_as_failed(str(e))
            raise

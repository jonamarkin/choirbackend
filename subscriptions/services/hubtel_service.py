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
from decimal import Decimal

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
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
            print(f"Hubtel response: {response_data}")

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
        Process Hubtel payment callback.

        Args:
            callback_data: Dict containing callback data from Hubtel
            request: Optional Django request object for IP validation

        Returns:
            Tuple (success: bool, message: str, transaction: PaymentTransaction or None)
        """
        try:
            # Validate IP address if request provided
            # if request and not self.validate_callback_ip(request):
            #     return False, "Invalid IP address", None

            # Extract client reference
            client_reference = callback_data.get('Data', {}).get('ClientReference')
            if not client_reference:
                return False, "Missing ClientReference in callback", None

            # Find transaction
            try:
                transaction = PaymentTransaction.objects.get(
                    client_reference=client_reference
                )
            except PaymentTransaction.DoesNotExist:
                return False, f"Transaction not found: {client_reference}", None

            # Check for duplicate callback
            if self.is_duplicate_callback(transaction, callback_data):
                return True, "Duplicate callback (already processed)", transaction

            # Process callback based on status
            response_code = callback_data.get('ResponseCode')
            status = callback_data.get('Status')
            data = callback_data.get('Data', {})

            if response_code == '0000' and status == 'Success' and data.get('Status') == 'Success':
                # Payment successful
                transaction.mark_as_success(callback_data)

                # Fetch additional fields from status check (non-blocking)
                try:
                    self.check_payment_status(transaction)
                except Exception as e:
                    logger.warning(f"Status check failed after callback success: {e}")

                return True, "Payment processed successfully", transaction

            else:
                # Payment failed
                error_message = data.get('Description', 'Payment failed')
                transaction.mark_as_failed(error_message, callback_data)
                return False, error_message, transaction

        except Exception as e:
            return False, f"Error processing callback: {str(e)}", None

    def check_payment_status(self, transaction):
        """
        Query Hubtel API for payment status.

        Args:
            transaction: PaymentTransaction instance

        Returns:
            Updated PaymentTransaction object

        Raises:
            requests.RequestException: If API call fails
        """
        # Build status check URL
        pos_sales_id = self.config['MERCHANT_ACCOUNT_NUMBER']
        url = f"{self.config['STATUS_API_URL']}/{pos_sales_id}/status"

        params = {'clientReference': transaction.client_reference}

        try:
            response = requests.get(
                url,
                params=params,
                headers={
                    'Authorization': self.get_auth_header(),
                    'Accept': 'application/json'
                },
                timeout=30
            )
            response.raise_for_status()

            response_data = response.json()
            logger.info(f"Hubtel status check response: {response_data}")

            # Check response
            if response_data.get('responseCode') == '0000':
                data = response_data.get('data', {})
                status = data.get('status')  # 'Paid', 'Unpaid', 'Refunded'

                if status == 'Paid':
                    # Update transaction with additional fields from status check
                    transaction.hubtel_transaction_id = data.get('transactionId', '')
                    transaction.network_transaction_id = data.get('externalTransactionId', '')
                    transaction.payment_type = data.get('paymentMethod', '')
                    transaction.charges = Decimal(str(data.get('charges', 0)))
                    transaction.amount_after_charges = Decimal(str(data.get('amountAfterCharges', 0)))

                    # Only mark as success if not already successful
                    if transaction.status != 'success':
                        callback_data = {'Data': data, 'ResponseCode': '0000', 'Status': 'Success'}
                        transaction.mark_as_success(callback_data)
                    else:
                        # Just save the additional fields
                        transaction.save()

                elif status == 'Unpaid':
                    # Still pending
                    transaction.status = 'pending'
                    transaction.save()

                elif status == 'Refunded':
                    # Refunded
                    transaction.status = 'refunded'
                    transaction.save()

            return transaction

        except requests.RequestException as e:
            # Log error but don't update transaction
            raise

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
        """Validate that callback is from Hubtel's whitelisted IP"""
        whitelisted_ips = self.config.get('WHITELISTED_IPS', [])

        if not whitelisted_ips:
            # If no IPs configured, allow all (for development)
            return True

        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')

        return ip in whitelisted_ips

    def is_duplicate_callback(self, transaction, callback_data):
        """
        Check if we've already processed this exact callback.
        Uses callback_data hash comparison.
        """
        if transaction.status in ['success', 'failed', 'refunded']:
            # Transaction already in final state
            callback_hash = hashlib.md5(
                json.dumps(callback_data, sort_keys=True).encode()
            ).hexdigest()

            if transaction.callback_data:
                existing_hash = hashlib.md5(
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
                    "callbackUrl": self.config['DIRECT_DEBIT_CALLBACK_URL'],
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

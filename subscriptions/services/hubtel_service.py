"""
Hubtel Payment Service
Handles all interactions with the Hubtel Online Checkout API.
"""
import base64
import hashlib
import json
import uuid
from datetime import timedelta
from decimal import Decimal

import requests
from django.conf import settings
from django.utils import timezone

from subscriptions.models import PaymentTransaction
from subscriptions.views.payment_views import logger


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

    def initiate_payment(self, user_subscription, amount=None, metadata=None):
        """
        Initiate payment with Hubtel.

        Args:
            user_subscription: UserSubscription instance
            amount: Payment amount (defaults to outstanding amount)
            metadata: Additional metadata dict

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
        payload = {
            "totalAmount": float(amount),
            "description": transaction.description,
            "callbackUrl": self.config['CALLBACK_URL'],
            "returnUrl": self.config['RETURN_URL'],
            "merchantAccountNumber": self.config['MERCHANT_ACCOUNT_NUMBER'],
            "cancellationUrl": self.config['CANCELLATION_URL'],
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

                if status == 'Paid' and transaction.status != 'success':
                    # Update transaction to success
                    transaction.hubtel_transaction_id = data.get('transactionId', '')
                    transaction.network_transaction_id = data.get('externalTransactionId', '')
                    transaction.payment_type = data.get('paymentMethod', '')
                    transaction.charges = Decimal(str(data.get('charges', 0)))
                    transaction.amount_after_charges = Decimal(str(data.get('amountAfterCharges', 0)))

                    # Mark as success
                    callback_data = {'Data': data, 'ResponseCode': '0000', 'Status': 'Success'}
                    transaction.mark_as_success(callback_data)

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

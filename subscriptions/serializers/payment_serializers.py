"""
Payment Serializers
Handles serialization for payment-related operations with Hubtel integration.
"""
from decimal import Decimal

from rest_framework import serializers

from subscriptions.models import PaymentTransaction, UserSubscription


class PaymentTransactionSerializer(serializers.ModelSerializer):
    """
    Serializer for PaymentTransaction model.
    Used for displaying payment transaction details.
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    subscription_name = serializers.CharField(source='user_subscription.subscription.name', read_only=True)
    outstanding_amount = serializers.SerializerMethodField()

    class Meta:
        model = PaymentTransaction
        fields = [
            'id',
            'client_reference',
            'checkout_id',
            'hubtel_transaction_id',
            'network_transaction_id',
            'sales_invoice_id',
            'user',
            'user_email',
            'user_name',
            'user_subscription',
            'subscription_name',
            'organization',
            'amount',
            'currency',
            'status',
            'checkout_url',
            'description',
            'payment_channel',
            'payment_type',
            'customer_mobile_number',
            'customer_name',
            'charges',
            'amount_after_charges',
            'initiated_at',
            'confirmed_at',
            'expires_at',
            'callback_received_at',
            'error_message',
            'retry_count',
            'notes',
            'created_at',
            'updated_at',
            'outstanding_amount',
        ]
        read_only_fields = [
            'id',
            'client_reference',
            'checkout_id',
            'hubtel_transaction_id',
            'network_transaction_id',
            'sales_invoice_id',
            'user',
            'user_subscription',
            'organization',
            'status',
            'checkout_url',
            'payment_channel',
            'payment_type',
            'customer_mobile_number',
            'customer_name',
            'charges',
            'amount_after_charges',
            'initiated_at',
            'confirmed_at',
            'expires_at',
            'callback_received_at',
            'callback_data',
            'created_at',
            'updated_at',
        ]

    def get_user_name(self, obj):
        """Get full name of user"""
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email
        return None

    def get_outstanding_amount(self, obj):
        """Get remaining outstanding amount after this payment"""
        if obj.status == 'success':
            return float(obj.user_subscription.get_outstanding_amount())
        return None


class PaymentInitiateSerializer(serializers.Serializer):
    """
    Serializer for initiating a payment.
    Validates input for payment initiation.
    """
    user_subscription_id = serializers.UUIDField(required=True)
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
        help_text="Amount to pay (defaults to outstanding amount)"
    )
    metadata = serializers.JSONField(
        required=False,
        allow_null=True,
        help_text="Additional metadata for the transaction"
    )
    return_url = serializers.URLField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="URL to redirect after successful payment (for mobile deep links, use app scheme e.g., myapp://payment-success)"
    )
    cancellation_url = serializers.URLField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="URL to redirect after cancelled payment (for mobile deep links, use app scheme e.g., myapp://payment-cancelled)"
    )

    def validate_user_subscription_id(self, value):
        """Validate that user subscription exists and belongs to current user"""
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("Authentication required")

        try:
            user_subscription = UserSubscription.objects.get(id=value)
        except UserSubscription.DoesNotExist:
            raise serializers.ValidationError("User subscription not found")

        # Verify ownership
        if user_subscription.user != request.user:
            raise serializers.ValidationError("You do not have permission to pay for this subscription")

        return value

    def validate_amount(self, value):
        """Validate payment amount"""
        if value is not None:
            if value <= 0:
                raise serializers.ValidationError("Amount must be greater than zero")
        return value

    def validate(self, data):
        """Cross-field validation"""
        user_subscription_id = data.get('user_subscription_id')
        amount = data.get('amount')

        try:
            user_subscription = UserSubscription.objects.get(id=user_subscription_id)
        except UserSubscription.DoesNotExist:
            raise serializers.ValidationError({"user_subscription_id": "User subscription not found"})

        # Check if user can make payment
        can_pay, message = user_subscription.can_make_payment()
        if not can_pay:
            raise serializers.ValidationError({"user_subscription_id": message})

        # Validate amount against outstanding
        outstanding = user_subscription.get_outstanding_amount()

        if amount is None:
            # Will use outstanding amount
            if outstanding <= 0:
                raise serializers.ValidationError({"amount": "No outstanding amount to pay"})
        else:
            # Validate provided amount
            if amount > outstanding:
                raise serializers.ValidationError({
                    "amount": f"Amount ({amount}) exceeds outstanding amount ({outstanding})"
                })

        return data


class PaymentInitiateResponseSerializer(serializers.Serializer):
    """
    Serializer for payment initiation response.
    """
    transaction_id = serializers.UUIDField()
    client_reference = serializers.CharField()
    checkout_url = serializers.URLField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
    expires_at = serializers.DateTimeField()
    description = serializers.CharField()


class PaymentWebhookSerializer(serializers.Serializer):
    """
    Serializer for validating Hubtel webhook callbacks.
    """
    ResponseCode = serializers.CharField(required=True)
    Status = serializers.CharField(required=True)
    Data = serializers.DictField(required=True)

    def validate_Data(self, value):
        """Validate required fields in Data object"""
        required_fields = ['ClientReference', 'Status', 'Amount']
        missing_fields = [field for field in required_fields if field not in value]

        if missing_fields:
            raise serializers.ValidationError(f"Missing required fields in Data: {', '.join(missing_fields)}")

        return value


class PaymentStatusSerializer(serializers.Serializer):
    """
    Serializer for payment status response.
    """
    transaction_id = serializers.UUIDField()
    client_reference = serializers.CharField()
    status = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
    payment_channel = serializers.CharField(allow_blank=True)
    payment_type = serializers.CharField(allow_blank=True)
    confirmed_at = serializers.DateTimeField(allow_null=True)
    error_message = serializers.CharField(allow_blank=True)


class UserSubscriptionPaymentInfoSerializer(serializers.ModelSerializer):
    """
    Serializer for user subscription with payment information.
    Includes user details for admin views.
    """
    # User fields
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()

    # Subscription fields
    subscription_name = serializers.CharField(source='subscription.name', read_only=True)
    subscription_description = serializers.CharField(source='subscription.description', read_only=True)
    subscription_amount = serializers.DecimalField(
        source='subscription.amount',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    # Payment info
    outstanding_amount = serializers.SerializerMethodField()
    payment_count = serializers.SerializerMethodField()
    payment_history = serializers.SerializerMethodField()
    can_make_payment = serializers.SerializerMethodField()
    payment_progress_percentage = serializers.SerializerMethodField()

    class Meta:
        model = UserSubscription
        fields = [
            'id',
            'user',
            'user_email',
            'user_name',
            'subscription',
            'subscription_name',
            'subscription_description',
            'subscription_amount',
            'status',
            'amount_paid',
            'outstanding_amount',
            'payment_count',
            'payment_date',
            'payment_reference',
            'payment_history',
            'can_make_payment',
            'payment_progress_percentage',
            'start_date',
            'end_date',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_user_name(self, obj):
        """Get full name of user"""
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email
        return None

    def get_outstanding_amount(self, obj):
        """Get outstanding amount"""
        return float(obj.get_outstanding_amount())

    def get_payment_count(self, obj):
        """Get number of successful payments"""
        return obj.payment_transactions.filter(status='success').count()

    def get_payment_history(self, obj):
        """Get payment history"""
        payments = obj.get_payment_history()[:5]  # Limit to last 5 payments
        return [{
            'amount': float(payment.amount),
            'date': payment.confirmed_at,
            'reference': payment.client_reference,
            'channel': payment.payment_channel,
            'type': payment.payment_type,
        } for payment in payments]

    def get_can_make_payment(self, obj):
        """Check if payment can be made"""
        can_pay, message = obj.can_make_payment()
        return {
            'allowed': can_pay,
            'message': message
        }

    def get_payment_progress_percentage(self, obj):
        """Calculate payment progress percentage"""
        if obj.subscription.amount > 0:
            progress = (obj.amount_paid / obj.subscription.amount) * 100
            return min(float(progress), 100.0)
        return 0.0

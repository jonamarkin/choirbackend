import uuid
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from authentication.models import User
from core.models import Organization, TenantAwareModel, TimestampedModel
from subscriptions.utils.assignees_categorizations import AssigneesCategorizations


class Subscription(TenantAwareModel, TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text="e.g., Annual Membership 2024")
    description = models.TextField()
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Subscription amount in the organization's currency"
    )
    start_date = models.DateField(help_text="When this subscription period starts")
    end_date = models.DateField(help_text="When this subscription period ends")
    assignees_category = models.CharField(
        _("category"),
        max_length=255,
        choices=AssigneesCategorizations.choices(),
        default=AssigneesCategorizations.BOTH.value,
        help_text="Who this subscription applies to: EXECUTIVES, MEMBERS, or BOTH"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this subscription is currently available for signup"
    )

    class Meta:
        db_table = 'subscriptions'
        ordering = ['-start_date', 'name']
        verbose_name = 'Subscription'
        verbose_name_plural = 'Subscriptions'
        indexes = [
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        return f"{self.name} ({self.organization.name})"

    def assign_to_users(self):
        """
        Automatically assign this subscription to users based on assignees_category.
        Creates UserSubscription records for all matching users.
        """
        # Get users based on category
        users = self._get_eligible_users()

        # Bulk create UserSubscription instances
        user_subscriptions = []
        for user in users:
            # Skip if user already has this subscription
            if not UserSubscription.objects.filter(user=user, subscription=self).exists():
                user_subscriptions.append(
                    UserSubscription(
                        user=user,
                        subscription=self,
                        status='not_paid'  # Default status when auto-assigned
                    )
                )

        # Bulk create to optimize database calls
        if user_subscriptions:
            UserSubscription.objects.bulk_create(user_subscriptions)

        return len(user_subscriptions)

    def _get_eligible_users(self):
        """Get users eligible for this subscription based on assignees_category"""
        base_query = User.objects.filter(organization=self.organization, is_active=True)

        if self.assignees_category == 'EXECUTIVES':
            # Only executive users
            return base_query.filter(
                role__in=['super_admin', 'admin', 'finance_admin', 'attendance_officer', 'treasurer']
            )
        elif self.assignees_category == 'MEMBERS':
            # Only regular members (non-executives)
            return base_query.filter(role='member')
        else:  # BOTH
            # All users
            return base_query


@receiver(post_save, sender=Subscription)
def auto_assign_subscription(sender, instance, created, **kwargs):
    """
    Signal to automatically assign subscription to users when created.
    """
    if created:
        # Automatically assign to eligible users when subscription is created
        instance.assign_to_users()


@receiver(post_save, sender=User)
def assign_subscriptions_to_new_user(sender, instance, created, **kwargs):
    """
    Signal to automatically assign existing active subscriptions to newly created users.
    This ensures that subscriptions created before the user existed still apply to them.
    """
    if created and instance.organization:
        # Get all active subscriptions for the user's organization
        active_subscriptions = Subscription.objects.filter(
            organization=instance.organization,
            is_active=True
        )
        
        # Determine user's role category
        executive_roles = ['super_admin', 'admin', 'finance_admin', 'attendance_officer', 'treasurer']
        is_executive = instance.role in executive_roles
        
        user_subscriptions = []
        for subscription in active_subscriptions:
            # Check if user is eligible based on assignees_category
            if subscription.assignees_category == 'EXECUTIVES' and not is_executive:
                continue
            elif subscription.assignees_category == 'MEMBERS' and is_executive:
                continue
            # 'BOTH' applies to everyone
            
            # Skip if user already has this subscription (shouldn't happen for new users, but safety check)
            if not UserSubscription.objects.filter(user=instance, subscription=subscription).exists():
                user_subscriptions.append(
                    UserSubscription(
                        user=instance,
                        subscription=subscription,
                        status='not_paid'
                    )
                )
        
        # Bulk create to optimize database calls
        if user_subscriptions:
            UserSubscription.objects.bulk_create(user_subscriptions)


class UserSubscription(TimestampedModel):
    """
    Individual user's subscription to a specific subscription period.
    Tracks payment status and individual subscription details.
    """
    STATUS_CHOICES = [
        ('fully_paid', 'Pending Payment'),
        ('partially_paid', 'Active'),
        ('overdue', 'Overdue'),
        ('not_paid', 'Not Paid'),
        ('refunded', 'Refunded'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_subscriptions'
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='user_subscriptions'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Amount actually paid (may differ from subscription amount)"
    )
    payment_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the payment was received"
    )
    payment_reference = models.CharField(
        max_length=255,
        blank=True,
        help_text="Payment reference/transaction ID"
    )
    notes = models.TextField(
        blank=True,
        help_text="Any additional notes about this subscription"
    )

    class Meta:
        db_table = 'user_subscriptions'
        unique_together = [['user', 'subscription']]
        ordering = ['-created_at']
        verbose_name = 'User Subscription'
        verbose_name_plural = 'User Subscriptions'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['subscription', 'status']),
            models.Index(fields=['payment_date']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.subscription.name} ({self.status})"

    @property
    def start_date(self):
        return self.subscription.start_date

    @property
    def end_date(self):
        return self.subscription.end_date

    def is_currently_active(self):
        from django.utils import timezone
        today = timezone.now().date()
        return (
                self.status == 'active'
                and self.subscription.start_date <= today <= self.subscription.end_date
        )

    def process_payment(self, amount_paid, payment_reference):
        """
        Process a payment and update subscription status.
        Called when a payment transaction succeeds.
        """
        from django.utils import timezone
        from decimal import Decimal

        # Update cumulative amount paid
        self.amount_paid += Decimal(str(amount_paid))
        self.payment_date = timezone.now()
        self.payment_reference = payment_reference

        # Update status based on amount paid
        subscription_amount = self.subscription.amount

        if self.amount_paid >= subscription_amount:
            self.status = 'fully_paid'
        elif self.amount_paid > 0:
            self.status = 'partially_paid'

        self.save()

    def get_outstanding_amount(self):
        """Calculate remaining amount to be paid"""
        from decimal import Decimal
        outstanding = self.subscription.amount - self.amount_paid
        return max(Decimal('0'), outstanding)

    def get_payment_history(self):
        """Get all successful payment transactions for this subscription"""
        return self.payment_transactions.filter(status='success').order_by('-confirmed_at')

    def can_make_payment(self):
        """Check if user can make another payment"""
        # Can't pay if already fully paid
        if self.status == 'fully_paid':
            return False, "Subscription is already fully paid"

        # Can't pay if refunded
        if self.status == 'refunded':
            return False, "Subscription has been refunded"

        # Check if there's a pending payment (within last 5 minutes)
        from django.utils import timezone
        from datetime import timedelta

        five_minutes_ago = timezone.now() - timedelta(minutes=1)
        pending_payment = self.payment_transactions.filter(
            status__in=['initiated', 'pending'],
            created_at__gte=five_minutes_ago
        ).exists()

        if pending_payment:
            return False, "A payment is already in progress. Please wait 5 minutes before trying again."

        return True, "Can make payment"


class PaymentTransaction(TimestampedModel):
    """
    Tracks individual payment transactions/attempts via Hubtel.
    One UserSubscription can have multiple PaymentTransactions (for partial payments).
    """

    TRANSACTION_STATUS_CHOICES = [
        ('initiated', 'Payment Initiated'),
        ('pending', 'Pending Confirmation'),
        ('success', 'Payment Successful'),
        ('failed', 'Payment Failed'),
        ('expired', 'Payment Expired'),
        ('cancelled', 'Payment Cancelled'),
        ('refunded', 'Payment Refunded'),
    ]

    # Primary Key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
    user_subscription = models.ForeignKey(
        'UserSubscription',
        on_delete=models.CASCADE,
        related_name='payment_transactions',
        help_text="The user subscription this payment is for"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payment_transactions',
        help_text="Denormalized for quick queries"
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='payment_transactions',
        help_text="Denormalized for multi-tenant queries"
    )

    # Hubtel Transaction Identifiers
    checkout_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Hubtel's checkout ID from initiate response"
    )
    client_reference = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Our unique reference for this transaction (max 32 chars per Hubtel)"
    )
    hubtel_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Hubtel's internal transaction ID (from callback)"
    )
    network_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Mobile network's transaction ID (externalTransactionId)"
    )
    sales_invoice_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Hubtel's SalesInvoiceId from callback"
    )

    # Payment Details
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Amount for this specific payment attempt"
    )
    currency = models.CharField(
        max_length=3,
        default='GHS',
        help_text="Currency code (GHS, USD, etc.)"
    )
    status = models.CharField(
        max_length=20,
        choices=TRANSACTION_STATUS_CHOICES,
        default='initiated'
    )

    # Hubtel Response Data
    checkout_url = models.URLField(
        blank=True,
        max_length=500,
        help_text="URL to redirect user to Hubtel checkout"
    )
    description = models.CharField(
        max_length=255,
        help_text="Payment description shown to user"
    )

    # Payment Method Details (from callback)
    payment_channel = models.CharField(
        max_length=50,
        blank=True,
        help_text="e.g., mtn-gh, vodafone-gh, card"
    )
    payment_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="e.g., mobilemoney, card"
    )
    customer_mobile_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Customer's mobile number used for payment"
    )
    customer_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Customer name from payment provider"
    )

    # Charges and Fees
    charges = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Transaction charges/fees from Hubtel"
    )
    amount_after_charges = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Amount after charges deduction"
    )

    # Timestamps
    initiated_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When payment was initiated"
    )
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When payment was confirmed/completed"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this payment attempt expires (5 mins from initiation)"
    )

    # Callback/Webhook Data
    callback_received_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When we received Hubtel's callback"
    )
    callback_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Raw callback data from Hubtel for debugging"
    )

    # Error Handling
    error_message = models.TextField(
        blank=True,
        help_text="Error message if payment failed"
    )
    retry_count = models.IntegerField(
        default=0,
        help_text="Number of times user retried this payment"
    )

    # Metadata
    metadata = models.JSONField(
        null=True,
        blank=True,
        help_text="Additional metadata (IP address, user agent, etc.)"
    )
    notes = models.TextField(
        blank=True,
        help_text="Admin notes about this transaction"
    )

    class Meta:
        db_table = 'payment_transactions'
        ordering = ['-created_at']
        verbose_name = 'Payment Transaction'
        verbose_name_plural = 'Payment Transactions'
        indexes = [
            models.Index(fields=['user_subscription', 'status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['client_reference']),
            models.Index(fields=['hubtel_transaction_id']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['initiated_at']),
            models.Index(fields=['confirmed_at']),
        ]

    def __str__(self):
        return f"{self.client_reference} - {self.amount} {self.currency} ({self.status})"

    def is_expired(self):
        """Check if payment has expired (5 minutes rule)"""
        if self.expires_at:
            from django.utils import timezone
            return timezone.now() > self.expires_at
        return False

    def mark_as_success(self, callback_data=None):
        """Mark transaction as successful and update related models"""
        from django.utils import timezone

        self.status = 'success'
        self.confirmed_at = timezone.now()
        self.callback_received_at = timezone.now()

        if callback_data:
            self.callback_data = callback_data
            # Extract payment details from callback
            payment_details = callback_data.get('Data', {}).get('PaymentDetails', {})
            self.payment_channel = payment_details.get('Channel', '')
            self.payment_type = payment_details.get('PaymentType', '')
            self.customer_mobile_number = payment_details.get('MobileMoneyNumber', '')
            self.sales_invoice_id = callback_data.get('Data', {}).get('SalesInvoiceId', '')

        self.save()

        # Update UserSubscription
        self.user_subscription.process_payment(self.amount, self.client_reference)

    def mark_as_failed(self, error_message='', callback_data=None):
        """Mark transaction as failed"""
        from django.utils import timezone

        self.status = 'failed'
        self.error_message = error_message
        self.callback_received_at = timezone.now()
        if callback_data:
            self.callback_data = callback_data
        self.save()
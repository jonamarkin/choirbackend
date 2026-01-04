from django.contrib import admin
from subscriptions.models import Subscription, UserSubscription, PaymentTransaction


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'amount', 'start_date', 'end_date', 'assignees_category', 'is_active']
    list_filter = ['organization', 'assignees_category', 'is_active', 'start_date']
    search_fields = ['name', 'description', 'organization__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'organization', 'name', 'description', 'amount')
        }),
        ('Period', {
            'fields': ('start_date', 'end_date')
        }),
        ('Settings', {
            'fields': ('assignees_category', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class PaymentTransactionInline(admin.TabularInline):
    """Inline display of payment transactions in UserSubscription admin"""
    model = PaymentTransaction
    extra = 0
    can_delete = False
    readonly_fields = [
        'client_reference',
        'amount',
        'status',
        'payment_channel',
        'payment_type',
        'initiated_at',
        'confirmed_at',
        'error_message'
    ]
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'subscription',
        'status',
        'amount_paid',
        'outstanding_amount',
        'payment_count',
        'payment_date',
        'created_at'
    ]
    list_filter = ['status', 'subscription__organization', 'payment_date']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'subscription__name', 'payment_reference']
    readonly_fields = ['id', 'created_at', 'updated_at', 'start_date', 'end_date', 'outstanding_amount', 'payment_count']
    inlines = [PaymentTransactionInline]

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'subscription')
        }),
        ('Period (from Subscription)', {
            'fields': ('start_date', 'end_date')
        }),
        ('Payment Information', {
            'fields': (
                'status',
                'amount_paid',
                'outstanding_amount',
                'payment_count',
                'payment_date',
                'payment_reference'
            )
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def outstanding_amount(self, obj):
        """Display outstanding amount"""
        return f"{obj.get_outstanding_amount()}"
    outstanding_amount.short_description = 'Outstanding Amount'

    def payment_count(self, obj):
        """Display number of successful payments"""
        return obj.payment_transactions.filter(status='success').count()
    payment_count.short_description = 'Payment Count'


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'client_reference',
        'user',
        'organization',
        'amount',
        'currency',
        'status',
        'payment_channel',
        'initiated_at',
        'confirmed_at'
    ]

    list_filter = [
        'status',
        'payment_channel',
        'payment_type',
        'organization',
        'currency',
        'initiated_at',
        'confirmed_at'
    ]

    search_fields = [
        'client_reference',
        'checkout_id',
        'hubtel_transaction_id',
        'network_transaction_id',
        'sales_invoice_id',
        'user__email',
        'user__first_name',
        'user__last_name',
        'user_subscription__subscription__name',
        'customer_mobile_number'
    ]

    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'initiated_at',
        'confirmed_at',
        'callback_received_at',
        'checkout_id',
        'client_reference',
        'hubtel_transaction_id',
        'network_transaction_id',
        'sales_invoice_id',
        'callback_data'
    ]

    fieldsets = (
        ('Transaction Info', {
            'fields': (
                'id',
                'client_reference',
                'checkout_id',
                'hubtel_transaction_id',
                'network_transaction_id',
                'sales_invoice_id',
                'status'
            )
        }),
        ('Relationships', {
            'fields': (
                'user_subscription',
                'user',
                'organization'
            )
        }),
        ('Payment Details', {
            'fields': (
                'amount',
                'currency',
                'charges',
                'amount_after_charges',
                'description'
            )
        }),
        ('Payment Method', {
            'fields': (
                'payment_channel',
                'payment_type',
                'customer_mobile_number',
                'customer_name'
            )
        }),
        ('Hubtel URLs', {
            'fields': (
                'checkout_url',
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'initiated_at',
                'confirmed_at',
                'callback_received_at',
                'expires_at',
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',)
        }),
        ('Error Handling', {
            'fields': (
                'error_message',
                'retry_count'
            )
        }),
        ('Metadata', {
            'fields': (
                'callback_data',
                'metadata',
                'notes'
            ),
            'classes': ('collapse',)
        })
    )

    actions = ['mark_as_success', 'mark_as_failed']

    def mark_as_success(self, request, queryset):
        """Admin action to manually mark pending payments as successful"""
        count = 0
        for transaction in queryset.filter(status__in=['pending', 'initiated']):
            transaction.mark_as_success()
            count += 1
        self.message_user(request, f'{count} transaction(s) marked as successful')
    mark_as_success.short_description = "Mark selected as successful"

    def mark_as_failed(self, request, queryset):
        """Admin action to manually mark payments as failed"""
        count = 0
        for transaction in queryset.filter(status__in=['pending', 'initiated']):
            transaction.mark_as_failed('Manually marked as failed by admin')
            count += 1
        self.message_user(request, f'{count} transaction(s) marked as failed')
    mark_as_failed.short_description = "Mark selected as failed"

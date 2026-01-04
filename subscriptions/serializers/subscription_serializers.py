from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from subscriptions.models import Subscription, UserSubscription
from subscriptions.utils.assignees_categorizations import AssigneesCategorizations


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for Subscription model"""
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    assigned_users_count = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            'id', 'organization', 'organization_name', 'name', 'description',
            'amount', 'start_date', 'end_date', 'assignees_category',
            'is_active', 'assigned_users_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']

    def get_assigned_users_count(self, obj):
        """Get count of users assigned to this subscription"""
        return obj.user_subscriptions.count()

    def validate(self, data):
        """Validate subscription dates"""
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError({
                    'end_date': 'End date must be after start date'
                })
        return data

    @transaction.atomic
    def create(self, validated_data):
        """Create subscription with automatic organization assignment"""
        user = self.context['request'].user

        # Check permissions
        if not user.is_executive():
            raise PermissionDenied('Only executive users can create subscriptions')

        # Assign organization from authenticated user
        validated_data['organization'] = user.organization

        return Subscription.objects.create(**validated_data)


class UserSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for UserSubscription model"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    subscription_name = serializers.CharField(source='subscription.name', read_only=True)
    subscription_amount = serializers.DecimalField(
        source='subscription.amount',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    start_date = serializers.DateField(read_only=True)
    end_date = serializers.DateField(read_only=True)
    is_currently_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = UserSubscription
        fields = [
            'id', 'user', 'user_email', 'user_name',
            'subscription', 'subscription_name', 'subscription_amount',
            'status', 'amount_paid', 'payment_date', 'payment_reference',
            'start_date', 'end_date', 'is_currently_active',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_user_name(self, obj):
        """Get user's full name"""
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username

    def validate(self, data):
        """Validate user subscription"""
        user = data.get('user', getattr(self.instance, 'user', None))
        subscription = data.get('subscription', getattr(self.instance, 'subscription', None))

        if user and subscription:
            if user.organization != subscription.organization:
                raise serializers.ValidationError({
                    'user': 'User and subscription must belong to the same organization'
                })

        if data.get('amount_paid') and subscription:
            if data['amount_paid'] > subscription.amount:
                raise serializers.ValidationError({
                    'amount_paid': f'Amount paid cannot exceed subscription amount of {subscription.amount}'
                })
        return data

from rest_framework import serializers

from subscriptions.models import DirectDebit, UserSubscription
from subscriptions.utils.auto_debit_period_types import AutoDebitPeriodTypes
from wallet.models import MobileWallet


class RegisterDirectDebitRequestSerializer(serializers.Serializer):
    subscription_id = serializers.UUIDField(required=True)
    wallet_id = serializers.UUIDField(required=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    period_type = serializers.CharField(required=True)

    def validate_period_type(self, value):
        try:
            return AutoDebitPeriodTypes.from_string(value).value
        except ValueError:
            raise serializers.ValidationError('Invalid period type.')

    def validate_wallet_id(self, value):
        user = self.context['request'].user
        wallet = MobileWallet.objects.filter(id=value, user=user).first()
        if wallet is None:
            raise serializers.ValidationError('Wallet not found.')
        if not wallet.is_active or wallet.verified_at is None:
            raise serializers.ValidationError('Wallet must be active and verified.')
        return wallet

    def validate_subscription_id(self, value):
        user = self.context['request'].user
        user_subscription = UserSubscription.objects.filter(
            user=user, subscription_id=value
        ).first()
        if user_subscription is None:
            raise serializers.ValidationError('You are not subscribed to this subscription.')
        return user_subscription


class DirectDebitListSerializer(serializers.ModelSerializer):
    subscription_name = serializers.CharField(
        source='user_subscription.subscription.name', read_only=True
    )

    class Meta:
        model = DirectDebit
        fields = [
            'id',
            'user_subscription',
            'subscription_name',
            'wallet',
            'amount',
            'period_type',
            'approval_status',
            'is_active',
            'next_payment_date',
        ]
        read_only_fields = fields


class DirectDebitResponseSerializer(serializers.ModelSerializer):
    subscription_name = serializers.CharField(
        source='user_subscription.subscription.name', read_only=True
    )
    wallet_account_number = serializers.CharField(source='wallet.account_number', read_only=True)
    wallet_network = serializers.CharField(source='wallet.network', read_only=True)

    class Meta:
        model = DirectDebit
        fields = [
            'id',
            'user_subscription',
            'subscription_name',
            'wallet',
            'wallet_account_number',
            'wallet_network',
            'amount',
            'period_type',
            'approval_status',
            'is_active',
            'next_payment_date',
            'previous_payment_date',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class DirectDebitUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DirectDebit
        fields = ['amount']


class DirectDebitStatusRequestSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=True)


class DirectDebitOtpVerificationRequestSerializer(serializers.Serializer):
    otp = serializers.CharField(required=True)

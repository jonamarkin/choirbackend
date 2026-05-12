from django.db import IntegrityError
from django.utils import timezone
from rest_framework import serializers

from authentication.services import OTPService
from wallet.models import MobileWallet
from wallet.utils.normalization import normalize_wallet_account_number


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = MobileWallet
        fields = [
            'id',
            'name',
            'description',
            'network',
            'account_number',
            'is_active',
            'verified_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'network',
            'account_number',
            'is_active',
            'verified_at',
            'created_at',
            'updated_at',
        ]


class WalletBaseInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    network = serializers.CharField(max_length=20)
    account_number = serializers.CharField(max_length=20)

    def validate_network(self, value):
        normalized = value.strip().upper()
        valid_networks = {choice[0] for choice in MobileWallet._meta.get_field('network').choices}
        if normalized not in valid_networks:
            raise serializers.ValidationError('Invalid wallet network.')
        return normalized

    def validate_account_number(self, value):
        return normalize_wallet_account_number(value)

    def validate(self, attrs):
        account_number = attrs['account_number']
        if MobileWallet.objects.filter(account_number=account_number).exists():
            raise serializers.ValidationError({
                'account_number': 'This wallet number is already in use.'
            })
        return attrs


class WalletOTPRequestSerializer(WalletBaseInputSerializer):
    pass


class WalletVerifyCreateSerializer(WalletBaseInputSerializer):
    otp_code = serializers.CharField(max_length=6)

    def create_wallet(self, user):
        validated = self.validated_data
        otp = OTPService.verify_otp(
            target=validated['account_number'],
            code=validated['otp_code'],
            purpose='wallet_verification',
        )
        if otp is None:
            raise serializers.ValidationError({'otp_code': 'Invalid or expired OTP.'})

        try:
            return MobileWallet.objects.create(
                user=user,
                name=validated['name'],
                description=validated.get('description') or '',
                network=validated['network'],
                account_number=validated['account_number'],
                is_active=True,
                verified_at=timezone.now(),
            )
        except IntegrityError:
            raise serializers.ValidationError({
                'account_number': 'This wallet number is already in use.'
            })


class WalletUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MobileWallet
        fields = ['name', 'description']


class WalletReactivationOTPRequestSerializer(serializers.Serializer):
    pass


class WalletVerifyReactivationSerializer(serializers.Serializer):
    otp_code = serializers.CharField(max_length=6)

    def reactivate_wallet(self, wallet):
        otp = OTPService.verify_otp(
            target=wallet.account_number,
            code=self.validated_data['otp_code'],
            purpose='wallet_verification',
        )
        if otp is None:
            raise serializers.ValidationError({'otp_code': 'Invalid or expired OTP.'})

        wallet.verified_at = timezone.now()
        wallet.is_active = True
        wallet.save(update_fields=['verified_at', 'is_active', 'updated_at'])
        return wallet

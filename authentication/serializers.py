from rest_framework import serializers
from django.contrib.auth import get_user_model
from dj_rest_auth.registration.serializers import RegisterSerializer as BaseRegisterSerializer
from .models import SocialAuthConnection

User = get_user_model()


class UserSubscriptionSummarySerializer(serializers.Serializer):
    """Lightweight serializer for user's subscription summary"""
    id = serializers.UUIDField(read_only=True)
    subscription_id = serializers.UUIDField(source='subscription.id', read_only=True)
    subscription_name = serializers.CharField(source='subscription.name', read_only=True)
    amount = serializers.DecimalField(source='subscription.amount', max_digits=10, decimal_places=2, read_only=True)
    start_date = serializers.DateField(read_only=True)
    end_date = serializers.DateField(read_only=True)
    status = serializers.CharField(read_only=True)
    amount_paid = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    payment_date = serializers.DateTimeField(read_only=True)
    is_currently_active = serializers.BooleanField(read_only=True)


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    organization_name = serializers.CharField(
        source='organization.name',
        read_only=True,
        allow_null=True
    )
    has_organization = serializers.BooleanField(read_only=True)
    subscriptions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'phone_number', 'profile_picture', 'role', 'auth_method',
            'organization', 'organization_name', 'has_organization',
            'email_verified', 'is_active', 'subscriptions',
            'created_at', 'last_login_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'last_login_at', 'email_verified',
            'auth_method'
        ]

    def get_subscriptions(self, obj):
        """Get user's subscriptions"""
        user_subscriptions = obj.user_subscriptions.select_related('subscription').all()
        return UserSubscriptionSummarySerializer(user_subscriptions, many=True).data


class RegisterSerializer(BaseRegisterSerializer):
    """Custom registration serializer"""
    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, max_length=150)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    organization_code = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Organization invite code (optional)"
    )

    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data.update({
            'first_name': self.validated_data.get('first_name', ''),
            'last_name': self.validated_data.get('last_name', ''),
            'phone_number': self.validated_data.get('phone_number', ''),
            'organization_code': self.validated_data.get('organization_code', ''),
        })
        return data

    def save(self, request):
        user = super().save(request)
        user.first_name = self.validated_data.get('first_name', '')
        user.last_name = self.validated_data.get('last_name', '')
        user.phone_number = self.validated_data.get('phone_number', '')
        user.auth_method = 'email'

        # Handle organization invite code
        org_code = self.validated_data.get('organization_code')
        if org_code:
            from core.models import Organization
            try:
                org = Organization.objects.get(slug=org_code)
                user.organization = org
            except Organization.DoesNotExist:
                pass

        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for login request"""
    email = serializers.EmailField(required=False)
    username = serializers.CharField(required=False)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        username = attrs.get('username')

        if not email and not username:
            raise serializers.ValidationError(
                "Either email or username is required"
            )

        return attrs

class LogoutSerializer(serializers.Serializer):
    """Serializer for logout request"""
    refresh = serializers.CharField(required=True)

    def validate(self, attrs):
        refresh = attrs.get('refresh')
        if not refresh:
            raise serializers.ValidationError("Refresh token required")
        return attrs

class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change"""
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)
    new_password_confirm = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': "Passwords do not match"
            })
        return attrs


class SocialAuthSerializer(serializers.Serializer):
    """Serializer for social auth"""
    provider = serializers.ChoiceField(
        choices=['google', 'github', 'microsoft']
    )
    access_token = serializers.CharField(required=True)
    code = serializers.CharField(required=False)


class SocialAuthConnectionSerializer(serializers.ModelSerializer):
    """Serializer for social auth connections"""

    class Meta:
        model = SocialAuthConnection
        fields = ['id', 'provider', 'created_at']
        read_only_fields = ['id', 'created_at']
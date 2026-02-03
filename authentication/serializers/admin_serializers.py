from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class AdminUserListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for admin user listing"""
    organization_name = serializers.CharField(
        source='organization.name',
        read_only=True,
        allow_null=True
    )

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'phone_number', 'role', 'member_part',
            'is_active', 'is_approved', 'email_verified', 'filled_form',
            'organization', 'organization_name',
            'created_at', 'last_login_at'
        ]
        read_only_fields = fields


class AdminUserDetailSerializer(serializers.ModelSerializer):
    """Full serializer for admin user detail view"""
    organization_name = serializers.CharField(
        source='organization.name',
        read_only=True,
        allow_null=True
    )

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'phone_number', 'profile_picture', 'role', 'auth_method',
            'organization', 'organization_name',
            'email_verified', 'is_active', 'is_approved', 'filled_form',
            'member_part', 'gender', 'date_of_birth', 'denomination',
            'address', 'join_date', 'employment_status', 'occupation', 'employer',
            'emergency_contact_name', 'emergency_contact_relationship', 'emergency_contact_phone',
            'created_at', 'updated_at', 'last_login_at'
        ]
        read_only_fields = [
            'id', 'email', 'username', 'auth_method',
            'email_verified', 'created_at', 'updated_at', 'last_login_at'
        ]


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user fields by admin"""

    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'phone_number',
            'role', 'member_part', 'is_active', 'is_approved',
            'gender', 'date_of_birth', 'denomination', 'address', 'join_date',
            'employment_status', 'occupation', 'employer',
            'emergency_contact_name', 'emergency_contact_relationship', 'emergency_contact_phone'
        ]

    def validate_role(self, value):
        """Prevent non-super_admins from assigning super_admin role"""
        request = self.context.get('request')
        if value == 'super_admin' and request:
            if not request.user.is_super_admin():
                raise serializers.ValidationError(
                    "Only super admins can assign the super_admin role."
                )
        return value

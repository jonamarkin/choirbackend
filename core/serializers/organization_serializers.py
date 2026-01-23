import logging

from django.db import transaction
from rest_framework import serializers

from authentication.serializers.user_serializers import OrganizationUserSerializer
from core.models import Organization

logger = logging.getLogger(__name__)


class OrganizationSerializer(serializers.ModelSerializer):
    members = OrganizationUserSerializer(source='users', many=True, read_only=True)

    class Meta:
        model = Organization
        fields = [
            'id', 'name', 'slug', 'contact_email', 'contact_phone',
            'is_active', 'subscription_tier', 'created_at', 'updated_at', 'code',
            'members'
        ]


class CreateOrganizationSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=True)
    contact_email = serializers.EmailField()
    contact_phone = serializers.CharField(required=True)
    subscription_tier = serializers.CharField()
    code = serializers.CharField(read_only=True)

    class Meta:
        model = Organization
        fields = [
            'name', 'contact_email', 'contact_phone', 'subscription_tier', 'code', 'slug'
        ]

    @transaction.atomic
    def create(self, validated_data):
        validated_data['code'] = Organization.generate_organization_code()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('code', None)
        return super().update(instance, validated_data)


class AddOrganizationMemberSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


from rest_framework import serializers
from core.models import ContactGroup, Contact
from authentication.models import User


class ContactSerializer(serializers.ModelSerializer):
    """Serializer for Contact model."""
    groups = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=ContactGroup.objects.all(),
        required=False
    )
    user_id = serializers.UUIDField(required=False, allow_null=True)
    
    class Meta:
        model = Contact
        fields = ['id', 'name', 'phone_number', 'groups', 'user_id', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        groups = validated_data.pop('groups', [])
        user_id = validated_data.pop('user_id', None)
        
        # Set organization from request user
        request = self.context.get('request')
        validated_data['organization'] = request.user.organization
        
        if user_id:
            validated_data['user'] = User.objects.get(id=user_id)
        
        contact = Contact.objects.create(**validated_data)
        contact.groups.set(groups)
        return contact

    def update(self, instance, validated_data):
        groups = validated_data.pop('groups', None)
        user_id = validated_data.pop('user_id', None)
        
        if user_id:
            instance.user = User.objects.get(id=user_id)
        elif user_id is None and 'user_id' in self.initial_data:
            instance.user = None
            
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        if groups is not None:
            instance.groups.set(groups)
        
        return instance


class ContactGroupSerializer(serializers.ModelSerializer):
    """Serializer for ContactGroup model."""
    contact_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = ContactGroup
        fields = ['id', 'name', 'description', 'contact_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'contact_count', 'created_at', 'updated_at']

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['organization'] = request.user.organization
        return super().create(validated_data)


class ContactGroupDetailSerializer(ContactGroupSerializer):
    """Serializer for ContactGroup with contacts list."""
    contacts = ContactSerializer(many=True, read_only=True)
    
    class Meta(ContactGroupSerializer.Meta):
        fields = ContactGroupSerializer.Meta.fields + ['contacts']


class AddContactsToGroupSerializer(serializers.Serializer):
    """Serializer for adding contacts to a group."""
    contact_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text="List of contact IDs to add to the group"
    )


class RemoveContactsFromGroupSerializer(serializers.Serializer):
    """Serializer for removing contacts from a group."""
    contact_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text="List of contact IDs to remove from the group"
    )


class BulkCreateContactsSerializer(serializers.Serializer):
    """Serializer for bulk creating contacts."""
    contacts = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField()
        ),
        min_length=1,
        help_text="List of contacts with 'name' and 'phone_number' fields"
    )
    group_id = serializers.UUIDField(required=False, allow_null=True, help_text="Optional group to add contacts to")

    def validate_contacts(self, value):
        for contact in value:
            if 'name' not in contact or 'phone_number' not in contact:
                raise serializers.ValidationError("Each contact must have 'name' and 'phone_number' fields")
        return value


class MemberPhoneSerializer(serializers.ModelSerializer):
    """Serializer for fetching choir members with phone numbers for SMS."""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'full_name', 'phone_number', 'email', 'member_part', 'role']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.email

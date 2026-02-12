from rest_framework import serializers
from events.models import Event

class EventListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing events.
    """
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    attendance_count = serializers.SerializerMethodField()
    is_past = serializers.BooleanField(read_only=True)

    class Meta:
        model = Event
        fields = [
            'id', 'slug', 'title', 'event_type', 'event_type_display',
            'location', 'google_maps_link', 'start_datetime', 'end_datetime',
            'is_mandatory', 'status', 'status_display',
            'attendance_count', 'is_past'
        ]

    def get_attendance_count(self, obj):
        """Get count of attendance records"""
        return obj.attendances.count()


class EventSerializer(serializers.ModelSerializer):
    """
    Full serializer for event details.
    """
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    attendance_summary = serializers.SerializerMethodField()
    is_past = serializers.BooleanField(read_only=True)

    class Meta:
        model = Event
        fields = [
            'id', 'slug', 'title', 'description', 'event_type', 'event_type_display',
            'location', 'google_maps_link', 'start_datetime', 'end_datetime',
            'is_mandatory', 'target_voice_parts',
            'status', 'status_display',
            'created_by', 'created_by_name',
            'attendance_summary', 'is_past',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'created_by', 'created_at', 'updated_at']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip() or obj.created_by.email
        return None

    def get_attendance_summary(self, obj):
        return obj.get_attendance_summary()


class EventCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/updating events.
    """
    class Meta:
        model = Event
        fields = [
            'title', 'description', 'event_type',
            'location', 'google_maps_link', 'start_datetime', 'end_datetime',
            'is_mandatory', 'target_voice_parts', 'status'
        ]

    def validate(self, data):
        """Validate event dates"""
        start = data.get('start_datetime')
        end = data.get('end_datetime')

        if end and start and end <= start:
            raise serializers.ValidationError({
                'end_datetime': 'End datetime must be after start datetime.'
            })

        return data

    def validate_target_voice_parts(self, value):
        """Convert 'all' to None"""
        if value:
            # Check if "all" is in the list (case insensitive)
            if any(str(part).lower() == 'all' for part in value):
                return None
        return value

    def create(self, validated_data):
        """Create event with organization and created_by from context"""
        request = self.context.get('request')
        validated_data['organization'] = request.user.organization
        validated_data['created_by'] = request.user
        return super().create(validated_data)


class RecurringEventSerializer(serializers.Serializer):
    """
    Serializer for creating recurring events.
    """
    base_event = EventCreateSerializer()
    frequency = serializers.ChoiceField(choices=['daily', 'weekly', 'biweekly'])
    count = serializers.IntegerField(required=False, min_value=2, max_value=52, help_text="Number of events to create")
    until_date = serializers.DateField(required=False, help_text="Date to stop creating events")

    def validate(self, data):
        if not data.get('count') and not data.get('until_date'):
            raise serializers.ValidationError("Either 'count' or 'until_date' must be provided.")
        
        if data.get('count') and data.get('until_date'):
             raise serializers.ValidationError("Provide either 'count' or 'until_date', not both.")
             
        return data

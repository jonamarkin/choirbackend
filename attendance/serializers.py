"""
Event Serializers
Handles serialization for event and attendance-related operations.
"""
from rest_framework import serializers
from django.utils import timezone

from attendance.models import Event, EventAttendance, get_user_attendance_stats
from authentication.models import User


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
            'location', 'start_datetime', 'end_datetime',
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
            'location', 'start_datetime', 'end_datetime',
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
            'location', 'start_datetime', 'end_datetime',
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

    def create(self, validated_data):
        """Create event with organization and created_by from context"""
        request = self.context.get('request')
        validated_data['organization'] = request.user.organization
        validated_data['created_by'] = request.user
        return super().create(validated_data)


class EventAttendanceSerializer(serializers.ModelSerializer):
    """
    Serializer for viewing attendance records.
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    user_voice_part = serializers.CharField(source='user.member_part', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    marked_by_name = serializers.SerializerMethodField()
    event_title = serializers.CharField(source='event.title', read_only=True)

    class Meta:
        model = EventAttendance
        fields = [
            'id', 'event', 'event_title',
            'user', 'user_email', 'user_name', 'user_voice_part',
            'status', 'status_display',
            'marked_by', 'marked_by_name', 'marked_at',
            'notes', 'created_at'
        ]
        read_only_fields = ['id', 'marked_by', 'marked_at', 'created_at']

    def get_user_name(self, obj):
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email
        return None

    def get_marked_by_name(self, obj):
        if obj.marked_by:
            return f"{obj.marked_by.first_name} {obj.marked_by.last_name}".strip() or obj.marked_by.email
        return None


class MarkAttendanceSerializer(serializers.Serializer):
    """
    Serializer for marking single user attendance.
    """
    user_id = serializers.UUIDField(required=True)
    status = serializers.ChoiceField(
        choices=EventAttendance.ATTENDANCE_STATUS_CHOICES,
        required=True
    )
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_user_id(self, value):
        """Validate user exists and belongs to same organization"""
        request = self.context.get('request')
        try:
            user = User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")

        if user.organization != request.user.organization:
            raise serializers.ValidationError("User does not belong to your organization")

        return value


class BulkAttendanceSerializer(serializers.Serializer):
    """
    Serializer for marking attendance for multiple users at once.
    """
    attendances = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        help_text="List of {user_id, status, notes (optional)} objects"
    )

    def validate_attendances(self, value):
        """Validate all attendance entries"""
        request = self.context.get('request')
        valid_statuses = [choice[0] for choice in EventAttendance.ATTENDANCE_STATUS_CHOICES]

        validated = []
        for item in value:
            if 'user_id' not in item:
                raise serializers.ValidationError("Each attendance entry must have a user_id")
            if 'status' not in item:
                raise serializers.ValidationError("Each attendance entry must have a status")
            if item['status'] not in valid_statuses:
                raise serializers.ValidationError(f"Invalid status: {item['status']}")

            try:
                user = User.objects.get(id=item['user_id'])
                if user.organization != request.user.organization:
                    raise serializers.ValidationError(
                        f"User {item['user_id']} does not belong to your organization"
                    )
            except User.DoesNotExist:
                raise serializers.ValidationError(f"User not found: {item['user_id']}")

            validated.append({
                'user_id': item['user_id'],
                'status': item['status'],
                'notes': item.get('notes', '')
            })

        return validated


class AttendanceStatsSerializer(serializers.Serializer):
    """
    Serializer for user attendance statistics.
    """
    total_mandatory_events = serializers.IntegerField()
    events_attended = serializers.IntegerField()
    present = serializers.IntegerField()
    late = serializers.IntegerField()
    excused = serializers.IntegerField()
    absent = serializers.IntegerField()
    attendance_percentage = serializers.FloatField()


class MyAttendanceSerializer(serializers.ModelSerializer):
    """
    Serializer for user's own attendance history.
    """
    event_title = serializers.CharField(source='event.title', read_only=True)
    event_type = serializers.CharField(source='event.event_type', read_only=True)
    event_date = serializers.DateTimeField(source='event.start_datetime', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = EventAttendance
        fields = [
            'id', 'event', 'event_title', 'event_type', 'event_date',
            'status', 'status_display', 'notes', 'marked_at'
        ]

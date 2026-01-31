from rest_framework import serializers
from attendance.models import EventAttendance, get_user_attendance_stats
from authentication.models import User


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
        """Validate user exists and permissions"""
        request = self.context.get('request')
        try:
            user = User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")

        if user.organization != request.user.organization:
            raise serializers.ValidationError("User does not belong to your organization")
            
        # Permission Check for Part Leaders
        if request.user.role == 'part_leader':
            if request.user.member_part and user.member_part != request.user.member_part:
                raise serializers.ValidationError(f"As a Part Leader, you can only mark attendance for {request.user.get_member_part_display()}s.")

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
                
                # Permission Check for Part Leaders
                if request.user.role == 'part_leader':
                    if request.user.member_part and user.member_part != request.user.member_part:
                        raise serializers.ValidationError(
                            f"User {user.email} is not in your part ({request.user.get_member_part_display()})."
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

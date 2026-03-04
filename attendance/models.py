import uuid
from django.db import models
from django.utils import timezone
from authentication.models import User
from core.models import TimestampedModel
from events.models import Event


class EventAttendance(TimestampedModel):
    """
    Tracks individual member attendance for an event.
    """
    ATTENDANCE_STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('excused', 'Excused'),
        ('late', 'Late'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='attendances',
        help_text="The event this attendance record is for"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='event_attendances',
        help_text="The member whose attendance is being tracked"
    )
    status = models.CharField(
        max_length=20,
        choices=ATTENDANCE_STATUS_CHOICES,
        default='absent',
        help_text="Attendance status"
    )
    marked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='marked_attendances',
        help_text="User who marked this attendance"
    )
    marked_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the attendance was marked"
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this attendance record"
    )

    class Meta:
        db_table = 'event_attendances'
        ordering = ['-marked_at']
        verbose_name = 'Event Attendance'
        verbose_name_plural = 'Event Attendances'
        unique_together = [['event', 'user']]
        indexes = [
            models.Index(fields=['event', 'status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['marked_at']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.event.title} ({self.get_status_display()})"


def get_user_attendance_stats(user, organization=None):
    """
    Calculate attendance statistics for a user.
    """
    from django.db.models import Q
    from django.utils import timezone
    
    def is_event_targeted_to_user(event_obj):
        """
        Voice-part targeting semantics:
        - null/blank target => all members
        - ['all'] => all members
        - otherwise member_part must be explicitly listed
        """
        targets = event_obj.target_voice_parts
        if not targets:
            return True

        normalized_targets = {
            str(part).strip().lower()
            for part in targets
            if str(part).strip()
        }
        if 'all' in normalized_targets:
            return True

        member_part = (user.member_part or '').strip().lower()
        return bool(member_part and member_part in normalized_targets)

    # Base query for events
    scoped_organization = user.organization if organization is None else organization
    events_query = Event.objects.filter(
        organization=scoped_organization,
        is_mandatory=True,
    ).exclude(
        status='cancelled'
    ).filter(
        Q(status='completed') | Q(start_datetime__lte=timezone.now())
    )

    eligible_event_ids = []
    for event in events_query.only('id', 'target_voice_parts'):
        if is_event_targeted_to_user(event):
            eligible_event_ids.append(event.id)

    # If attendance has already been marked for the user on an event that is
    # outside the default mandatory/eligible scope (e.g. non-mandatory or
    # future-dated but explicitly marked), include it so stats stay consistent
    # with attendance history shown to the user.
    marked_event_ids = set()
    marked_events_query = Event.objects.filter(
        attendances__user=user,
        organization=scoped_organization,
    ).exclude(
        status='cancelled'
    ).only(
        'id', 'target_voice_parts'
    ).distinct()
    for event in marked_events_query:
        marked_event_ids.add(event.id)

    eligible_event_ids = list(set(eligible_event_ids) | marked_event_ids)

    total_events = len(eligible_event_ids)
    
    # Get attendance records
    attendance_query = EventAttendance.objects.filter(
        user=user,
        event_id__in=eligible_event_ids
    )
    
    present_count = attendance_query.filter(status='present').count()
    late_count = attendance_query.filter(status='late').count()
    excused_count = attendance_query.filter(status='excused').count()
    absent_count = attendance_query.filter(status='absent').count()
    
    # Calculate percentage (present + late counts as attended)
    attended = present_count + late_count
    attendance_percentage = round((attended / total_events * 100), 1) if total_events > 0 else 0.0
    
    return {
        'total_mandatory_events': total_events,
        'events_attended': attended,
        'present': present_count,
        'late': late_count,
        'excused': excused_count,
        'absent': absent_count,
        'attendance_percentage': attendance_percentage
    }

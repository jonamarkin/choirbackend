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
    
    # Base query for events
    events_query = Event.objects.filter(
        organization=user.organization if organization is None else organization,
        is_mandatory=True,
        status='completed'
    )
    
    # Filter by voice part if applicable
    if user.member_part:
        events_query = events_query.filter(
            Q(target_voice_parts__isnull=True) | 
            Q(target_voice_parts__contains=[user.member_part])
        )
    else:
        events_query = events_query.filter(target_voice_parts__isnull=True)
    
    total_events = events_query.count()
    
    # Get attendance records
    attendance_query = EventAttendance.objects.filter(
        user=user,
        event__in=events_query
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

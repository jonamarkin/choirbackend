import uuid
from django.db import models
from django.utils import timezone
from authentication.models import User
from core.models import Organization, TenantAwareModel, TimestampedModel


class Event(TenantAwareModel, TimestampedModel):
    """
    Represents a choir event such as rehearsal, concert, or program attendance.
    """
    EVENT_TYPE_CHOICES = [
        ('rehearsal', 'Rehearsal'),
        ('funeral', 'Funeral'),
        ('wedding', 'Wedding'),
        ('corporate', 'Corporate Event'),
        ('concert', 'Concert'),
        ('church_service', 'Church Service'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    VOICE_PART_CHOICES = [
        ('soprano', 'Soprano'),
        ('alto', 'Alto'),
        ('tenor', 'Tenor'),
        ('bass', 'Bass'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, help_text="Event title")
    description = models.TextField(blank=True, help_text="Event description")
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES,
        default='rehearsal',
        help_text="Type of event"
    )
    location = models.CharField(max_length=255, blank=True, help_text="Event location")
    start_datetime = models.DateTimeField(help_text="Event start date and time")
    end_datetime = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Event end date and time (optional)"
    )
    is_mandatory = models.BooleanField(
        default=True,
        help_text="Whether attendance is mandatory for this event"
    )
    target_voice_parts = models.JSONField(
        null=True,
        blank=True,
        help_text="List of voice parts this event is targeted at (e.g., ['soprano', 'alto']). Null means all parts."
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        blank=True,
        help_text="URL-friendly identifier"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_events',
        help_text="User who created this event"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled',
        help_text="Current status of the event"
    )

    class Meta:
        db_table = 'events'
        ordering = ['-start_datetime']
        verbose_name = 'Event'
        verbose_name_plural = 'Events'
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['organization', 'event_type']),
            models.Index(fields=['start_datetime']),
            models.Index(fields=['organization', 'start_datetime']),
            models.Index(fields=['slug']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            import random
            import string
            
            # Generate base slug from title
            base_slug = slugify(self.title)
            if not base_slug:
                base_slug = "event"
                
            # Append 4 random chars to ensure uniqueness
            random_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
            self.slug = f"{base_slug}-{random_chars}"
            
            # Ensure uniqueness loop (just in case)
            while Event.objects.filter(slug=self.slug).exists():
                random_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
                self.slug = f"{base_slug}-{random_chars}"
                
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.get_event_type_display()}) - {self.start_datetime.strftime('%Y-%m-%d')}"

    def is_past(self):
        """Check if event has already occurred"""
        return self.start_datetime < timezone.now()

    def get_attendance_summary(self):
        """Get summary of attendance for this event"""
        attendances = self.attendances.all()
        total = attendances.count()
        present = attendances.filter(status='present').count()
        late = attendances.filter(status='late').count()
        absent = attendances.filter(status='absent').count()
        excused = attendances.filter(status='excused').count()

        return {
            'total_marked': total,
            'present': present,
            'late': late,
            'absent': absent,
            'excused': excused,
            'attendance_rate': round((present + late) / total * 100, 1) if total > 0 else 0
        }

    def get_eligible_members(self):
        """Get members who should attend this event based on target_voice_parts"""
        from authentication.models import User
        
        base_query = User.objects.filter(
            organization=self.organization,
            is_active=True
        )
        
        if self.target_voice_parts:
            return base_query.filter(member_part__in=self.target_voice_parts)
        return base_query


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
    
    Args:
        user: User instance
        organization: Optional organization to filter by
    
    Returns:
        Dictionary with attendance statistics
    """
    from django.db.models import Count, Q
    
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

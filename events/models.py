import uuid
from django.db import models
from django.utils import timezone
from authentication.models import User
from core.models import TenantAwareModel, TimestampedModel


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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(
        max_length=255,
        unique=True,
        blank=True,
        help_text="URL-friendly identifier"
    )
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
            models.Index(fields=['organization', 'slug']),
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
            
            # Ensure uniqueness loop
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

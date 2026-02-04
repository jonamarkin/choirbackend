import uuid
from django.db import models
from core.models import TenantAwareModel, TimestampedModel

class ContactGroup(TenantAwareModel, TimestampedModel):
    """
    Groups for organizing contacts for bulk SMS sending.
    Organization-scoped for multi-tenancy.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Group name (e.g., 'Alto Section', 'Event Volunteers')")
    description = models.TextField(blank=True, help_text="Optional description of the group")

    class Meta:
        db_table = 'contact_groups'
        ordering = ['name']
        unique_together = [['organization', 'name']]

    def __str__(self):
        return f"{self.name} ({self.organization.name})"

    @property
    def contact_count(self):
        return self.contacts.count()


class Contact(TenantAwareModel, TimestampedModel):
    """
    Individual contact for SMS sending.
    Can optionally belong to groups and/or link to a User.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text="Contact name")
    phone_number = models.CharField(max_length=20, help_text="Phone number for SMS")
    
    # Optional group membership (many-to-many)
    groups = models.ManyToManyField(
        ContactGroup,
        related_name='contacts',
        blank=True,
        help_text="Groups this contact belongs to"
    )
    
    # Optional link to a User (choir member)
    user = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contact_entries',
        help_text="Link to choir member if applicable"
    )

    class Meta:
        db_table = 'contacts'
        ordering = ['name']
        indexes = [
            models.Index(fields=['organization', 'phone_number']),
        ]

    def __str__(self):
        return f"{self.name} ({self.phone_number})"

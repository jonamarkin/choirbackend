import random

from django.db import models
import uuid
from django.utils import timezone

class Organization(models.Model):
    """
    Multi-tenancy: Each choir/organization is a separate tenant.
    All data belongs to an organization.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text="Organization name (e.g., VocalEssence Chorale)")
    slug = models.SlugField(unique=True, help_text="URL-friendly name (e.g., vocalessence)")
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    subscription_tier = models.CharField(max_length=50, default='free')
    code = models.CharField(max_length=4, blank=False, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def generate_organization_code(cls):
        while True:
            code = str(random.randint(1000, 9999))
            if not cls.objects.filter(code=code).exists():
                return code
    
    class Meta:
        db_table = 'organizations'
        ordering = ['name']
        verbose_name = 'Organization'
        verbose_name_plural = 'Organizations'
    
    def __str__(self):
        return self.name


class TenantAwareModel(models.Model):
    """
    Abstract base model for all tenant-aware models.
    Automatically adds organization foreign key to any model that inherits it.
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='%(class)s_set'
    )
    
    class Meta:
        abstract = True  # This won't create a table


class TimestampedModel(models.Model):
    """Abstract model to add created/updated timestamps"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """Abstract model for soft delete functionality"""
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        abstract = True
    
    def soft_delete(self):
        """Mark as deleted without removing from database"""
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore a soft-deleted record"""
        self.deleted_at = None
        self.save()
    
    @property
    def is_deleted(self):
        return self.deleted_at is not None


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

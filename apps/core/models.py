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
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
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



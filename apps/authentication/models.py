import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model extending Django's AbstractUser.
    Links users to organizations for multi-tenancy.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Link to organization
    organization = models.ForeignKey(
        'core.Organization',
        on_delete=models.CASCADE,
        related_name='users'
    )
    
    # Additional fields
    phone_number = models.CharField(max_length=20, blank=True)
    
    # Role-based access control
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('admin', 'Admin'),
        ('finance_admin', 'Finance Admin'),
        ('attendance_officer', 'Attendance Officer'),
    ]
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='admin')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.username} ({self.organization.name})"
    
    def is_super_admin(self):
        return self.role == 'super_admin'
    
    def is_finance_admin(self):
        return self.role == 'finance_admin'
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model with organization support and social auth.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Link to organization (optional for social signups)
    organization = models.ForeignKey(
        'core.Organization',
        on_delete=models.CASCADE,
        related_name='users',
        null=True,
        blank=True
    )

    # Override email to be required and unique
    email = models.EmailField(unique=True)

    # Additional fields
    phone_number = models.CharField(max_length=20, blank=True)
    profile_picture = models.URLField(blank=True, null=True)

    # Auth method tracking
    AUTH_METHOD_CHOICES = [
        ('email', 'Email/Password'),
        ('google', 'Google'),
        ('github', 'GitHub'),
        ('microsoft', 'Microsoft'),
    ]
    auth_method = models.CharField(
        max_length=20,
        choices=AUTH_METHOD_CHOICES,
        default='email'
    )

    # Role-based access control (organization-level roles)
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('admin', 'Admin'),
        ('finance_admin', 'Finance Admin'),
        ('attendance_officer', 'Attendance Officer'),
        ('treasurer', 'Treasurer'),
        ('member', 'Member'),
    ]
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='member')

    # Email verification
    email_verified = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['organization', 'role']),
        ]

    def __str__(self):
        org_name = self.organization.name if self.organization else "No Org"
        return f"{self.email} ({org_name})"

    def is_system_admin(self):
        """Platform-level admin - uses Django's built-in is_superuser"""
        return self.is_superuser

    def is_super_admin(self):
        return self.role == 'super_admin' or self.is_superuser

    def is_finance_admin(self):
        return self.role == 'finance_admin' or self.is_superuser

    def is_attendance_officer(self):
        return self.role == 'attendance_officer' or self.is_superuser

    def is_treasurer(self):
        return self.role == 'treasurer' or self.is_superuser

    def has_organization(self):
        return self.organization is not None

    def is_executive(self):
        return self.role in ['super_admin', 'finance_admin', 'attendance_officer', 'treasurer', 'admin']


# Social Account Connection Model
class SocialAuthConnection(models.Model):
    """Track social auth connections for users"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='social_connections')
    provider = models.CharField(max_length=50)  # google, github, microsoft
    provider_user_id = models.CharField(max_length=255)
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'social_auth_connections'
        unique_together = [['provider', 'provider_user_id']]

    def __str__(self):
        return f"{self.user.email} - {self.provider}"
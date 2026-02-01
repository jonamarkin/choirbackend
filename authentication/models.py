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
        ('part_leader', 'Part Leader'),
        ('member', 'Member'),
    ]
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='member')

    # Email verification and Admin Approval
    email_verified = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False, help_text="Designates whether this user has been approved by an admin.")
    filled_form = models.BooleanField(default=False, help_text="Designates whether this user has completed their profile after registration.")

    # Member Profile Fields
    MEMBER_PART_CHOICES = [
        ('soprano', 'Soprano'),
        ('alto', 'Alto'),
        ('tenor', 'Tenor'),
        ('bass', 'Bass'),
        ('instrumentalist', 'Instrumentalist'),
        ('directorate', 'Directorate'),
    ]
    member_part = models.CharField(
        max_length=20,
        choices=MEMBER_PART_CHOICES,
        blank=True,
        help_text="Voice part in the choir"
    )

    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]
    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
        blank=True,
        help_text="Gender of the member"
    )

    date_of_birth = models.DateField(
        null=True,
        blank=True,
        help_text="Date of birth"
    )

    denomination = models.CharField(
        max_length=100,
        blank=True,
        help_text="Religious denomination"
    )

    address = models.TextField(
        blank=True,
        help_text="Home address"
    )

    join_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date the member joined the choir"
    )

    # Employment Information
    EMPLOYMENT_STATUS_CHOICES = [
        ('employed', 'Employed'),
        ('self_employed', 'Self Employed'),
        ('student', 'Student'),
        ('unemployed', 'Unemployed'),
        ('retired', 'Retired'),
    ]
    employment_status = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_STATUS_CHOICES,
        blank=True,
        help_text="Current employment status"
    )

    occupation = models.CharField(
        max_length=100,
        blank=True,
        help_text="Occupation or profession"
    )

    employer = models.CharField(
        max_length=255,
        blank=True,
        help_text="Employer or institution name"
    )

    # Emergency Contact Information
    emergency_contact_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Emergency contact full name"
    )

    emergency_contact_relationship = models.CharField(
        max_length=50,
        blank=True,
        help_text="Relationship to emergency contact (e.g., spouse, parent, sibling)"
    )

    emergency_contact_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Emergency contact phone number"
    )

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

    def is_part_leader(self):
        return self.role == 'part_leader' or self.is_superuser

    def has_organization(self):
        return self.organization is not None

    def is_executive(self):
        return self.role in ['super_admin', 'finance_admin', 'attendance_officer', 'treasurer', 'admin', 'part_leader']


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


class OTP(models.Model):
    """
    One-Time Password (OTP) for multiple purposes (Activation, Reset, Login).
    Decoupled from User to support non-user verifications (e.g. phone number before signup).
    """
    PURPOSE_CHOICES = [
        ('activation', 'Account Activation'),
        ('password_reset', 'Password Reset'),
        ('login', 'Login Verification'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps', null=True, blank=True)
    target = models.CharField(max_length=255, help_text="Email or Phone number")
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default='activation')
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'otps'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['target', 'purpose']),
        ]

    def __str__(self):
        return f"{self.target} - {self.purpose} ({self.code})"

    def is_valid(self):
        """Check if OTP is valid (not expired and not used)"""
        from django.utils import timezone
        return not self.is_used and self.expires_at > timezone.now()

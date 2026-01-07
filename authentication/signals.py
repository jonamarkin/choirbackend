from allauth.account.signals import user_signed_up
from django.dispatch import receiver
from core.models import Organization

@receiver(user_signed_up)
def populate_profile(request, user, **kwargs):
    """
    Signal handler to perform actions after a user signs up.
    """
    # Assign default organization if not set
    if not user.organization:
        # Get the first organization (assuming there's only one or we want the default)
        default_org = Organization.objects.first()
        if default_org:
            user.organization = default_org
            user.save(update_fields=['organization'])

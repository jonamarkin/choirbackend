from django.db.models.signals import post_save
from django.dispatch import receiver

from authentication.models import User
from subscriptions.models import Subscription


@receiver(post_save, sender=Subscription)
def auto_assign_subscription(sender, instance, created, **kwargs):
    """
    Signal to automatically assign subscription to users when created.
    """
    if created:
        # Automatically assign to eligible users when subscription is created
        instance.assign_to_users()


@receiver(post_save, sender=User)
def auto_assign_existing_subscriptions_to_user(sender, instance, created, **kwargs):
    """
    Ensure users are assigned to already-existing active subscriptions.

    Why this is needed:
    - New users can be created before their organization is attached.
    - Registration/social flows may set organization on a later save.
    - Without this hook, those users can miss backfilled subscription assignment.
    """
    if kwargs.get('raw'):
        return

    if not instance.organization:
        return

    # On updates, skip obvious unrelated partial updates for efficiency.
    # If update_fields is None (full save), we still run because organization
    # and role may have changed.
    if not created:
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            relevant_fields = {'organization', 'role', 'is_active'}
            if relevant_fields.isdisjoint(set(update_fields)):
                return

    from subscriptions.services.subscription_service import assign_subscriptions_to_user
    assign_subscriptions_to_user(instance)

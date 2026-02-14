
from django.db import transaction
from subscriptions.models import Subscription, UserSubscription
from authentication.models import User

def assign_subscriptions_to_user(user: User):
    """
    Assign existing active subscriptions to a user based on their role and organization.
    This ensures that subscriptions created before the user existed still apply to them.
    
    Args:
        user: The user instance to assign subscriptions to.
    """
    if not user.organization:
        return 0

    # Get all active subscriptions for the user's organization
    active_subscriptions = Subscription.objects.filter(
        organization=user.organization,
        is_active=True
    )
    
    # Determine user's role category
    executive_roles = ['super_admin', 'admin', 'finance_admin', 'attendance_officer', 'treasurer']
    is_executive = user.role in executive_roles
    
    user_subscriptions = []
    for subscription in active_subscriptions:
        # Check if user is eligible based on assignees_category
        if subscription.assignees_category == 'EXECUTIVES' and not is_executive:
            continue
        elif subscription.assignees_category == 'MEMBERS' and is_executive:
            continue
        # 'BOTH' applies to everyone
        
        # Skip if user already has this subscription
        if not UserSubscription.objects.filter(user=user, subscription=subscription).exists():
            user_subscriptions.append(
                UserSubscription(
                    user=user,
                    subscription=subscription,
                    status='not_paid'
                )
            )
    
    # Bulk create to optimize database calls
    if user_subscriptions:
        UserSubscription.objects.bulk_create(user_subscriptions)
        
    return len(user_subscriptions)

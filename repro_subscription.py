
import os
import django
from datetime import date, timedelta
from django.db.models.signals import post_save

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "choirbackend.settings")
django.setup()

from authentication.models import User
from core.models import Organization
from subscriptions.models import Subscription, UserSubscription, AssigneesCategorizations
from subscriptions.services.subscription_service import assign_subscriptions_to_user

def test_subscription_assignment():
    print("Setting up test data...")
    # Clean up
    User.objects.filter(email='test_sub_bug@example.com').delete()
    Organization.objects.filter(name='Test Org for Bug').delete()

    # Create Org
    org = Organization.objects.create(name='Test Org for Bug', slug='test-org-bug')
    
    # Create Subscription
    sub = Subscription.objects.create(
        organization=org,
        name='Test Sub',
        amount=100,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=365),
        assignees_category=AssigneesCategorizations.BOTH.value,
        is_active=True
    )
    print(f"Created Subscription: {sub}")

    # Mimic Registration Flow
    print("Creating User without organization (simulating initial create)...")
    user = User.objects.create_user(
        username='test_sub_bug',
        email='test_sub_bug@example.com',
        password='password123'
    )
    
    print(f"User created. Org: {user.organization}")

    # Simulate populate_profile logic
    print("Assigning organization (simulating post-signup signal)...")
    user.organization = org
    user.save()
    
    # EXPLICITLY CALL THE SERVICE (This is what the signal now does)
    print("Calling assign_subscriptions_to_user service...")
    assign_subscriptions_to_user(user)

    print(f"User updated. Org: {user.organization}")

    # Check for UserSubscription
    has_sub = UserSubscription.objects.filter(user=user, subscription=sub).exists()
    print(f"Has Subscription? {has_sub}")

    if not has_sub:
        print("BUG STILL EXISTS: Subscription was NOT assigned.")
    else:
        print("SUCCESS: Subscription assigned correctly via service.")

if __name__ == "__main__":
    try:
        test_subscription_assignment()
    except Exception as e:
        print(f"Error: {e}")


import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'choirbackend.settings.base')
django.setup()

from django.test import RequestFactory
from rest_framework.views import APIView
from authentication.models import User
from authentication.permissions import IsApproved

class MockView(APIView):
    permission_classes = [IsApproved]

def test_approval_logic():
    print("Testing IsApproved Permission...")
    
    # Create a test user
    email = "test_approval@example.com"
    # Ensure cleanup from previous failed runs
    User.objects.filter(email=email).delete()
    
    user = User.objects.create_user(username="test_approval", email=email, password="password123")
    user.is_active = True
    user.is_approved = False # Default
    user.save()
    
    factory = RequestFactory()
    request = factory.get('/')
    request.user = user
    
    permission = IsApproved()
    view = MockView()
    
    # Test 1: Unapproved User
    has_perm = permission.has_permission(request, view)
    print(f"Unapproved User Access: {'ALLOWED' if has_perm else 'DENIED'} (Expected: DENIED)")
    
    # Test 2: Approved User
    user.is_approved = True
    user.save()
    has_perm = permission.has_permission(request, view)
    print(f"Approved User Access: {'ALLOWED' if has_perm else 'DENIED'} (Expected: ALLOWED)")
    
    # Cleanup
    user.delete()

if __name__ == "__main__":
    test_approval_logic()

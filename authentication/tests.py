from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from authentication.serializers.user_serializers import RegisterSerializer
from authentication.permissions import IsApproved
from rest_framework.views import APIView

User = get_user_model()

class AuthenticationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_register_serializer_sets_active_true(self):
        """Test that new users are created as active (is_active=True)."""
        data = {
            "email": "test_active_suite@example.com",
            "username": "test_active_suite",
            "password": "password123",
            "password1": "password123",
            "organization_code": ""
        }
        
        # Mocking a request context
        request = self.factory.post('/api/v1/auth/register/')
        
        serializer = RegisterSerializer(data=data, context={'request': request})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        user = serializer.save(request)
        self.assertTrue(user.is_active, "New users should be active by default")

    def test_is_approved_permission(self):
        """Test IsApproved permission logic."""
        user = User.objects.create_user(
            username="test_perm", 
            email="test_perm@example.com", 
            password="password123"
        )
        # Default state
        user.is_active = True
        user.is_approved = False
        user.save()

        permission = IsApproved()
        view = APIView()
        
        request = self.factory.get('/')
        request.user = user

        # Case 1: Unapproved
        self.assertFalse(permission.has_permission(request, view), 
                        "Unapproved user should NOT have permission")

        # Case 2: Approved
        user.is_approved = True
        user.save()
        self.assertTrue(permission.has_permission(request, view), 
                       "Approved user SHOULD have permission")

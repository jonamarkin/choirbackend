from unittest.mock import patch

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate
from authentication.serializers.user_serializers import RegisterSerializer
from authentication.permissions import IsApproved
from authentication.views.admin_views import AdminUserViewSet
from authentication.views.auth_views import AuthViewSet
from rest_framework.views import APIView
from core.models import Organization

User = get_user_model()


class AuthenticationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
    
    def _request_with_session(self, path):
        request = self.factory.post(path)
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        return request

    @patch('authentication.services.OTPService.generate_otp')
    def test_register_serializer_sets_active_false_pending_verification(self, _mock_otp):
        """New email/password users should be inactive until email verification."""
        data = {
            "email": "test_active_suite@example.com",
            "username": "test_active_suite",
            "password1": "password123",
            "password2": "password123",
            "organization_code": ""
        }

        request = self._request_with_session('/api/v1/auth/register/')
        serializer = RegisterSerializer(data=data, context={'request': request})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save(request)
        self.assertFalse(
            user.is_active,
            "New users should remain inactive until email verification",
        )

    @patch('authentication.services.OTPService.generate_otp')
    @patch('authentication.serializers.user_serializers.EmailService.send_pending_approval_email')
    def test_register_serializer_sends_pending_approval_email(self, mock_pending, _mock_otp):
        data = {
            "email": "notify_register@example.com",
            "username": "notify_register",
            "password1": "password123",
            "password2": "password123",
            "first_name": "Notify",
            "organization_code": "",
        }
        request = self._request_with_session('/api/v1/auth/register/')
        serializer = RegisterSerializer(data=data, context={'request': request})
        self.assertTrue(serializer.is_valid(), serializer.errors)

        user = serializer.save(request)
        mock_pending.assert_called_once_with(
            email=user.email,
            first_name=user.first_name,
        )

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


class AdminUserNotificationTests(TestCase):
    def setUp(self):
        self.api_factory = APIRequestFactory()
        self.organization = Organization.objects.create(
            name="Notify Org",
            slug="notify-org",
            contact_email="org@example.com",
            contact_phone="000111222",
            code="9001",
        )
        self.admin_user = User.objects.create_user(
            username="org_admin",
            email="org_admin@example.com",
            password="password123",
            organization=self.organization,
            role="admin",
        )
        self.member_user = User.objects.create_user(
            username="member_user",
            email="member_user@example.com",
            password="password123",
            organization=self.organization,
            role="member",
            is_active=True,
        )

    @patch('authentication.views.admin_views.EmailService.send_account_activated_email')
    def test_admin_activate_sends_email(self, mock_send):
        self.member_user.is_active = False
        self.member_user.save(update_fields=['is_active'])

        request = self.api_factory.post('/api/v1/auth/admin/users/x/activate')
        force_authenticate(request, user=self.admin_user)
        view = AdminUserViewSet.as_view({'post': 'activate'})

        response = view(request, pk=str(self.member_user.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send.assert_called_once_with(
            email=self.member_user.email,
            first_name=self.member_user.first_name,
        )

    @patch('authentication.views.admin_views.EmailService.send_account_deactivated_email')
    def test_admin_deactivate_sends_email(self, mock_send):
        request = self.api_factory.post('/api/v1/auth/admin/users/x/deactivate')
        force_authenticate(request, user=self.admin_user)
        view = AdminUserViewSet.as_view({'post': 'deactivate'})

        response = view(request, pk=str(self.member_user.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send.assert_called_once_with(
            email=self.member_user.email,
            first_name=self.member_user.first_name,
        )


class AuthActionNotificationTests(TestCase):
    def setUp(self):
        self.api_factory = APIRequestFactory()
        self.user = User.objects.create_user(
            username="notify_user",
            email="notify_user@example.com",
            password="old_password123",
            role="member",
            is_active=True,
        )
        self.organization = Organization.objects.create(
            name="Join Org",
            slug="join-org",
            contact_email="join@example.com",
            contact_phone="222111000",
            code="8123",
        )

    @patch('authentication.views.auth_views.EmailService.send_password_changed_email')
    def test_change_password_sends_email(self, mock_send):
        request = self.api_factory.post(
            '/api/v1/auth/change-password',
            {
                'old_password': 'old_password123',
                'new_password': 'new_password123',
                'new_password_confirm': 'new_password123',
            },
            format='json',
        )
        force_authenticate(request, user=self.user)
        view = AuthViewSet.as_view({'post': 'change_password'})

        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send.assert_called_once_with(
            email=self.user.email,
            first_name=self.user.first_name,
        )

    @patch('authentication.views.auth_views.EmailService.send_join_organization_email')
    def test_join_organization_sends_email(self, mock_send):
        request = self.api_factory.post(
            '/api/v1/auth/join-organization',
            {'organization_code': self.organization.code},
            format='json',
        )
        force_authenticate(request, user=self.user)
        view = AuthViewSet.as_view({'post': 'join_organization'})

        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send.assert_called_once_with(
            email=self.user.email,
            first_name=self.user.first_name,
            organization_name=self.organization.name,
        )

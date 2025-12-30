from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.github.views import GitHubOAuth2Adapter
from allauth.socialaccount.providers.microsoft.views import MicrosoftGraphOAuth2Adapter
from dj_rest_auth.registration.views import SocialLoginView

from .serializers import (
    LoginSerializer, UserSerializer, PasswordChangeSerializer,
    SocialAuthConnectionSerializer
)
from .models import SocialAuthConnection

User = get_user_model()


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Login with email/username and password.

    POST /api/v1/auth/login/
    {
        "email": "user@example.com",  // or "username": "username"
        "password": "password123"
    }
    """
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data.get('email')
    username = serializer.validated_data.get('username')
    password = serializer.validated_data['password']

    # Try to find user by email or username
    user = None
    if email:
        try:
            user = User.objects.get(email=email)
            username = user.username
        except User.DoesNotExist:
            pass

    # Authenticate
    user = authenticate(username=username, password=password)

    if user is None:
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    if not user.is_active:
        return Response(
            {'error': 'Account is inactive'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Update last login
    user.last_login_at = timezone.now()
    user.save(update_fields=['last_login_at'])

    # Generate JWT tokens
    refresh = RefreshToken.for_user(user)

    # Add custom claims
    if user.organization:
        refresh['organization_id'] = str(user.organization.id)
    refresh['role'] = user.role
    refresh['email'] = user.email

    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': UserSerializer(user).data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    Logout and blacklist refresh token.

    POST /api/v1/auth/logout/
    {
        "refresh": "refresh_token_here"
    }
    """
    try:
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'error': 'Refresh token required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        token = RefreshToken(refresh_token)
        token.blacklist()

        return Response({
            'message': 'Logout successful'
        })
    except Exception as e:
        return Response(
            {'error': 'Invalid token'},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    """
    Get current user information.

    GET /api/v1/auth/me/
    Headers: Authorization: Bearer <access_token>
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """
    Update current user profile.

    PUT/PATCH /api/v1/auth/profile/
    {
        "first_name": "John",
        "last_name": "Doe",
        "phone_number": "+233244123456"
    }
    """
    user = request.user
    serializer = UserSerializer(user, data=request.data, partial=True)

    if serializer.is_valid():
        # Prevent changing certain fields
        protected_fields = ['email', 'username', 'role', 'organization', 'auth_method']
        for field in protected_fields:
            if field in serializer.validated_data:
                serializer.validated_data.pop(field)

        serializer.save()
        return Response(serializer.data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change user password.

    POST /api/v1/auth/change-password/
    {
        "old_password": "old123",
        "new_password": "new123",
        "new_password_confirm": "new123"
    }
    """
    serializer = PasswordChangeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = request.user

    # Check old password
    if not user.check_password(serializer.validated_data['old_password']):
        return Response(
            {'error': 'Invalid old password'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Set new password
    user.set_password(serializer.validated_data['new_password'])
    user.save()

    return Response({
        'message': 'Password changed successfully'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def social_connections(request):
    """
    Get user's connected social accounts.

    GET /api/v1/auth/social-connections/
    """
    connections = SocialAuthConnection.objects.filter(user=request.user)
    serializer = SocialAuthConnectionSerializer(connections, many=True)
    return Response(serializer.data)


# Social Auth Views
class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter


class GitHubLogin(SocialLoginView):
    adapter_class = GitHubOAuth2Adapter


class MicrosoftLogin(SocialLoginView):
    adapter_class = MicrosoftGraphOAuth2Adapter
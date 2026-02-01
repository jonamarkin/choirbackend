from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, action, authentication_classes
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.github.views import GitHubOAuth2Adapter
from allauth.socialaccount.providers.microsoft.views import MicrosoftGraphOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView, RegisterView
# Password Reset (OTP) Views
from authentication.serializers.auth_serializers import RequestPasswordResetSerializer, PasswordResetVerifySerializer

class CustomOAuth2Client(OAuth2Client):
    """
    Custom OAuth2Client to resolve mismatch between dj-rest-auth and allauth.
    - Acccepts 'scope' but drops it (allauth removed it).
    - Ensures scope_delimiter is positional/keyword compatible.
    """

    def __init__(self, request, consumer_key, consumer_secret, access_token_method, access_token_url, callback_url,
                 scope=None, scope_delimiter=" ", headers=None, basic_auth=False):
        if scope_delimiter is None:
            scope_delimiter = " "
        # Pass only arguments supported by allauth's OAuth2Client
        super().__init__(request, consumer_key, consumer_secret, access_token_method, access_token_url, callback_url,
                         scope_delimiter, headers, basic_auth)


from authentication.serializers.user_serializers import (
    LoginSerializer, UserSerializer, PasswordChangeSerializer,
    SocialAuthConnectionSerializer, LogoutSerializer, JoinOrganizationSerializer
)
from core.serializers.organization_serializers import OrganizationSerializer

@extend_schema(tags=['Authentication'])
class CustomRegisterView(RegisterView):
    authentication_classes = []
    permission_classes = [AllowAny]


from authentication.models import SocialAuthConnection

User = get_user_model()


@extend_schema(tags=['Authentication'])
class AuthViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny, ]
    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.action == "login":
            return [AllowAny()]
        return [IsAuthenticated(), ]

    @extend_schema(request=LoginSerializer, responses={200: UserSerializer},
                   description="Login with email/username and password")
    @action(detail=False, methods=['post'], authentication_classes=[])
    def login(self, request):
        """
        Login with email/username and password.

        POST /api/v1/auth/login/
        {
            "email": "user@example.com", // or "username": "username"
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
            # Check if it was because of inactive user
            try:
                # We partially resolved user above, or try again
                user_obj = None
                if email:
                    user_obj = User.objects.get(email=email)
                elif username:
                    user_obj = User.objects.get(username=username)

                if user_obj and user_obj.check_password(password):
                    if not user_obj.is_active:
                        return Response(
                            {
                                'detail': 'Account created successfully. Your account is currently inactive pending admin approval.',
                                'code': 'account_inactive',
                                'user': UserSerializer(user_obj).data
                            },
                            status=status.HTTP_200_OK
                        )
            except User.DoesNotExist:
                pass

            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            # This block likely unreachable with default backend but good specific safety
            return Response(
                {
                    'detail': 'Account created successfully. Your account is currently inactive pending admin approval.',
                    'code': 'account_inactive',
                    'user': UserSerializer(user).data
                },
                status=status.HTTP_200_OK
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

    @extend_schema(request=LogoutSerializer, responses={200: None}, description="Logout and blacklist refresh token")
    @action(detail=False, methods=['post'])
    def logout(self, request):
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

    @extend_schema(responses={200: UserSerializer}, description="Get current user information")
    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        Get current user information.

        GET /api/v1/auth/me/
        Headers: Authorization: Bearer <access_token>
        """
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    @extend_schema(request=UserSerializer, responses={200: UserSerializer}, description="Update current user profile")
    @action(detail=False, methods=['put', 'patch'])
    def update_profile(self, request):
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

            # Mark that the user has filled the profile form
            serializer.save(filled_form=True)
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(request=PasswordChangeSerializer, responses={200: None}, description="Change user password")
    @action(detail=False, methods=['post'])
    def change_password(self, request):
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

    @extend_schema(responses={200: SocialAuthConnectionSerializer(many=True)},
                   description="Get user's connected social accounts")
    @action(detail=False, methods=['get'])
    def social_connections(self, request):
        """
        Get user's connected social accounts.

        GET /api/v1/auth/social-connections/
        """
        connections = SocialAuthConnection.objects.filter(user=request.user)
        serializer = SocialAuthConnectionSerializer(connections, many=True)
        return Response(serializer.data)

    @extend_schema(
        request=JoinOrganizationSerializer,
        responses={200: OrganizationSerializer},
        description="Join an organization using an invite code"
    )
    @action(detail=False, methods=['post'])
    def join_organization(self, request):
        """
        Join an organization using a 4-digit invite code.

        POST /api/v1/auth/join-organization/
        {
            "organization_code": "1234"
        }
        """
        serializer = JoinOrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user

        # Check if user already belongs to an organization
        if user.organization is not None:
            return Response(
                {'error': 'You already belong to an organization'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Find the organization by code
        from core.models import Organization
        org_code = serializer.validated_data['organization_code']
        try:
            organization = Organization.objects.get(code=org_code)
        except Organization.DoesNotExist:
            return Response(
                {'error': 'Invalid organization code'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Assign user to organization
        user.organization = organization
        user.save(update_fields=['organization'])

        return Response({
            'message': 'Successfully joined organization',
            'organization': OrganizationSerializer(organization).data
        })


# Social Auth Views
@extend_schema(tags=['Social Login'])
class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    client_class = CustomOAuth2Client
    authentication_classes = []
    permission_classes = [AllowAny]

    @property
    def callback_url(self):
        # Use callback_url from request if provided, otherwise default
        return self.request.data.get('callback_url', 'http://localhost:3000')


@extend_schema(tags=['Social Login'])
class GitHubLogin(SocialLoginView):
    adapter_class = GitHubOAuth2Adapter
    client_class = CustomOAuth2Client
    authentication_classes = []
    permission_classes = [AllowAny]

    @property
    def callback_url(self):
        return self.request.data.get('callback_url', 'http://localhost:3000')


@extend_schema(tags=['Social Login'])
class MicrosoftLogin(SocialLoginView):
    adapter_class = MicrosoftGraphOAuth2Adapter
    client_class = CustomOAuth2Client
    authentication_classes = []
    permission_classes = [AllowAny]

    @property
    def callback_url(self):
        return self.request.data.get('callback_url', 'http://localhost:3000')


@extend_schema(tags=['Social Login'])
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def social_account_signup(request):
    """
    Fallback view for allauth social account signup redirects.
    In an API-only context, we don't want to render a signup form.
    Instead, we return a JSON error indicating that the auto-signup process failed
    (likely due to missing information or a conflict).
    """
    return Response(
        {
            'error': 'Social account signup failed',
            'detail': 'Could not automatically create an account. This may be because an account with this email already exists (try logging in) or essential information is missing from the social provider.'
        },
        status=status.HTTP_400_BAD_REQUEST
    )


# Email Verification Views
from authentication.serializers.auth_serializers import VerifyEmailSerializer, ResendOTPSerializer
from authentication.services import OTPService

@extend_schema(
    request=VerifyEmailSerializer,
    responses={200: {'message': 'Email verified successfully'}},
    description="Verify email using OTP code"
)
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email(request):
    """
    Verify email account activation using 6-digit OTP.
    """
    serializer = VerifyEmailSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        # If user is not active, activate them
        if not user.is_active:
            user.is_active = True
            user.email_verified = True
            user.save()
            return Response({'message': 'Email verified successfully. You can now login.'}, status=status.HTTP_200_OK)
        else:
             return Response({'message': 'Email already verified.'}, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    request=ResendOTPSerializer,
    responses={200: {'message': 'OTP sent successfully'}},
    description="Resend activation OTP"
)
@api_view(['POST'])
@permission_classes([AllowAny])
def resend_otp(request):
    """
    Resend the activation OTP to the user's email.
    """
    serializer = ResendOTPSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        # Generate new OTP
        OTPService.generate_otp(target=email, purpose='activation', channel='email')
        return Response({'message': 'OTP sent successfully.'}, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




@extend_schema(
    request=RequestPasswordResetSerializer,
    responses={200: {'message': 'Password reset OTP sent.'}},
    description="Request OTP for password reset"
)
@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    """
    Step 1: Request OTP for password reset.
    """
    serializer = RequestPasswordResetSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        # Generate OTP for password reset
        OTPService.generate_otp(target=email, purpose='password_reset', channel='email')
        return Response({'message': 'Password reset OTP sent to your email.'}, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    request=PasswordResetVerifySerializer,
    responses={200: {'message': 'Password reset successfully.'}},
    description="Reset password using Verified OTP"
)
@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password_confirm(request):
    """
    Step 2: Reset password using OTP.
    """
    serializer = PasswordResetVerifySerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        new_password = serializer.validated_data['new_password']
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        return Response({'message': 'Password reset successfully. You can now login.'}, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

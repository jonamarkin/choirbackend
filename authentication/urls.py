from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from dj_rest_auth.views import PasswordResetView, PasswordResetConfirmView
from .views import auth_views, admin_views

router = DefaultRouter(trailing_slash=False)
router.register('', auth_views.AuthViewSet, basename='auth')

# Admin router for user management
admin_router = DefaultRouter(trailing_slash=False)
admin_router.register('users', admin_views.AdminUserViewSet, basename='admin-users')

urlpatterns = [

    path('', include(router.urls)),

    # JWT token refresh
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Registration (from dj-rest-auth)
    # Registration (custom view to disable auth check)
    path('register/', auth_views.CustomRegisterView.as_view(), name='rest_register'),
    path('register/', include('dj_rest_auth.registration.urls')),
    
    # Email Verification
    path('verify-email/', auth_views.verify_email, name='verify_email'),
    path('resend-otp/', auth_views.resend_otp, name='resend_otp'),

    # Password reset ONLY
    # Password Reset (OTP)
    path('password/reset/', auth_views.request_password_reset, name='password_reset_request'),
    path('password/reset/confirm/', auth_views.reset_password_confirm, name='password_reset_confirm'),

    # Social authentication
    path('social/google/', auth_views.GoogleLogin.as_view(), name='google_login'),
    path('social/google', auth_views.GoogleLogin.as_view(), name='google_login_no_slash'),
    path('social/github/', auth_views.GitHubLogin.as_view(), name='github_login'),
    path('social/github', auth_views.GitHubLogin.as_view(), name='github_login_no_slash'),
    path('social/microsoft/', auth_views.MicrosoftLogin.as_view(), name='microsoft_login'),
    path('social/microsoft', auth_views.MicrosoftLogin.as_view(), name='microsoft_login_no_slash'),

    # Admin endpoints for user management
    path('admin/', include(admin_router.urls)),
]

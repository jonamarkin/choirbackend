from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from dj_rest_auth.views import PasswordResetView, PasswordResetConfirmView
from . import views

router = DefaultRouter(trailing_slash=False)
router.register('', views.AuthViewSet, basename='auth')

urlpatterns = [

    path('', include(router.urls)),
    
    # JWT token refresh
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Registration (from dj-rest-auth)
    path('register/', include('dj_rest_auth.registration.urls')),
    
    # Password reset ONLY
    path('password/reset/', PasswordResetView.as_view(), name='password_reset'),
    path('password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    
    # Social authentication
    path('social/google/', views.GoogleLogin.as_view(), name='google_login'),
    path('social/github/', views.GitHubLogin.as_view(), name='github_login'),
    path('social/microsoft/', views.MicrosoftLogin.as_view(), name='microsoft_login'),
]
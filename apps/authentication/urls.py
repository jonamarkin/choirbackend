from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # Traditional auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # User management
    path('me/', views.me_view, name='me'),
    path('profile/', views.update_profile, name='update_profile'),
    path('change-password/', views.change_password, name='change_password'),
    path('social-connections/', views.social_connections, name='social_connections'),

    # Registration & password reset (from dj-rest-auth)
    path('register/', include('dj_rest_auth.registration.urls')),
    path('password-reset/', include('dj_rest_auth.urls')),

    # Social authentication
    path('social/google/', views.GoogleLogin.as_view(), name='google_login'),
    path('social/github/', views.GitHubLogin.as_view(), name='github_login'),
    path('social/microsoft/', views.MicrosoftLogin.as_view(), name='microsoft_login'),
]
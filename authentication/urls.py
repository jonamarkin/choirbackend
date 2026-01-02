from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

router = DefaultRouter(trailing_slash=False)
router.register('', views.AuthViewSet, basename='auth')

urlpatterns = [
    # Traditional auth
    path('', include(router.urls)),

    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Registration & password reset (from dj-rest-auth)
    path('register/', include('dj_rest_auth.registration.urls')),
    path('password-reset/', include('dj_rest_auth.urls')),

    # Social authentication
    path('social/google/', views.GoogleLogin.as_view(), name='google_login'),
    path('social/github/', views.GitHubLogin.as_view(), name='github_login'),
    path('social/microsoft/', views.MicrosoftLogin.as_view(), name='microsoft_login'),
]
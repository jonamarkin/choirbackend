"""
URL configuration for choirbackend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from authentication.views.auth_views import social_account_signup

from django.conf import settings
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)


v1_0_patterns = [
    path('auth/', include('authentication.urls')),
    path('subscriptions/', include('subscriptions.urls', namespace='subscriptions')),
    path('core/', include('core.urls')),
    path('attendance/', include('attendance.urls')),
]


urlpatterns = [
    path("admin/", admin.site.urls),

    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # API endpoints
    path('api/v1/', include((v1_0_patterns, 'v1.0'), namespace='v1.0')), # All API Endpoints (Should be in the v1_0_patterns list)
    # path('accounts/', include('allauth.urls')), 
    
    # Fallback for allauth redirect (Must be global/non-namespaced)
    path('social/signup/', social_account_signup, name='socialaccount_signup'),
]


if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns += [
            path('__debug__/', include(debug_toolbar.urls)),
        ]
    except ImportError:
        pass
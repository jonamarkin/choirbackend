from rest_framework.routers import DefaultRouter

from core.views import organization_views

router = DefaultRouter(trailing_slash=False)
router.register('organizations', organization_views.OrganizationViewSet, basename='organizations')

urlpatterns = router.urls

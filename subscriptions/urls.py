from django.urls import path
from rest_framework.routers import DefaultRouter

from .views.subscription_views import SubscriptionViewSet
from .views.payment_views import PaymentViewSet

app_name = 'subscriptions'
router = DefaultRouter(trailing_slash=False)

# Register viewsets
router.register('payments', PaymentViewSet, basename='payments')
router.register('', SubscriptionViewSet, basename='subscriptions')

# URL patterns
urlpatterns = router.urls
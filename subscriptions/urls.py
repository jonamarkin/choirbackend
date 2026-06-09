from django.urls import path
from rest_framework.routers import DefaultRouter

from .views.direct_debit_views import DirectDebitViewSet
from .views.subscription_views import SubscriptionViewSet
from .views.payment_views import PaymentViewSet

app_name = 'subscriptions'
router = DefaultRouter(trailing_slash=False)

# Register viewsets
router.register('payments', PaymentViewSet, basename='payments')
router.register('direct-debits', DirectDebitViewSet, basename='direct-debit')
# The empty-prefix route is greedy ('^(?P<pk>[^/.]+)$') and must be registered
# last so it does not shadow the more specific 'payments'/'direct-debits' routes.
router.register('', SubscriptionViewSet, basename='subscriptions')

# URL patterns
urlpatterns = router.urls
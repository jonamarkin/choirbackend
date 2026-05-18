from rest_framework.routers import DefaultRouter

from wallet.views import MobileWalletViewSet

router = DefaultRouter(trailing_slash=False)
router.register('', MobileWalletViewSet, basename='wallets')

urlpatterns = router.urls

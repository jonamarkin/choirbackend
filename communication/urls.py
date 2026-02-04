from rest_framework.routers import DefaultRouter

from communication.views import sms_views, contact_views

router = DefaultRouter()
router.register('sms', sms_views.SMSViewSet, basename='sms')
router.register('contact-groups', contact_views.ContactGroupViewSet, basename='contact-groups')
router.register('contacts', contact_views.ContactViewSet, basename='contacts')
router.register('members/phones', contact_views.MemberPhoneViewSet, basename='member-phones')

urlpatterns = router.urls

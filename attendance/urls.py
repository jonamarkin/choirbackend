from django.urls import path, include
from rest_framework.routers import DefaultRouter
from attendance.views import EventViewSet, MyAttendanceViewSet

router = DefaultRouter(trailing_slash=False)
router.register('events', EventViewSet, basename='events')
router.register('my-attendance', MyAttendanceViewSet, basename='my-attendance')

urlpatterns = [
    path('', include(router.urls)),
]

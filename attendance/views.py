from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from attendance.models import EventAttendance, get_user_attendance_stats
from attendance.serializers import (
    AttendanceStatsSerializer, MyAttendanceSerializer
)


@extend_schema(tags=['My Attendance'])
class MyAttendanceViewSet(viewsets.ViewSet):
    """
    ViewSet for viewing own attendance records and stats.
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={200: MyAttendanceSerializer(many=True)},
        description="Get your attendance history"
    )
    def list(self, request):
        """Get current user's attendance history"""
        attendances = EventAttendance.objects.filter(
            user=request.user
        ).select_related('event').order_by('-event__start_datetime')
        
        serializer = MyAttendanceSerializer(attendances, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        responses={200: AttendanceStatsSerializer},
        description="Get your attendance statistics"
    )
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get current user's attendance statistics"""
        if not request.user.organization:
            return Response({
                'error': 'You must belong to an organization to view attendance stats'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        stats = get_user_attendance_stats(request.user)
        serializer = AttendanceStatsSerializer(stats)
        return Response(serializer.data)

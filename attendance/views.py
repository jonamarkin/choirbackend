"""
Event Views
Handles API endpoints for event management and attendance tracking.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from attendance.models import Event, EventAttendance, get_user_attendance_stats
from attendance.serializers import (
    EventSerializer, EventListSerializer, EventCreateSerializer,
    EventAttendanceSerializer, MarkAttendanceSerializer, BulkAttendanceSerializer,
    AttendanceStatsSerializer, MyAttendanceSerializer
)
from authentication.models import User


class IsAdminOrAttendanceOfficer:
    """Custom permission check for attendance-related actions"""
    
    @staticmethod
    def has_permission(user):
        """Check if user can manage events/attendance"""
        return (
            user.is_superuser or
            user.role in ['super_admin', 'admin', 'attendance_officer']
        )


@extend_schema(tags=['Events'])
class EventViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing choir events.
    
    Actions:
    - list: Get all events for the organization
    - retrieve: Get single event details
    - create: Create new event (admin only)
    - update: Update event (admin only)
    - destroy: Delete event (admin only)
    """
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'
    
    def get_queryset(self):
        """Filter events by user's organization"""
        if not self.request.user.organization:
            return Event.objects.none()
        
        queryset = Event.objects.filter(organization=self.request.user.organization)
        
        # Apply filters
        event_type = self.request.query_params.get('event_type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        event_status = self.request.query_params.get('status')
        if event_status:
            queryset = queryset.filter(status=event_status)
        
        # Date filters
        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(start_datetime__date__gte=start_date)
        
        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(start_datetime__date__lte=end_date)
        
        # Upcoming events only
        upcoming = self.request.query_params.get('upcoming')
        if upcoming and upcoming.lower() == 'true':
            queryset = queryset.filter(start_datetime__gte=timezone.now())
        
        return queryset.order_by('-start_datetime')
    
    def get_serializer_class(self):
        if self.action == 'list':
            return EventListSerializer
        if self.action in ['create', 'update', 'partial_update']:
            return EventCreateSerializer
        return EventSerializer
    
    def check_admin_permission(self):
        """Check if user has admin permissions"""
        if not IsAdminOrAttendanceOfficer.has_permission(self.request.user):
            return Response(
                {'error': 'You do not have permission to perform this action'},
                status=status.HTTP_403_FORBIDDEN
            )
        return None
    
    @extend_schema(
        parameters=[
            OpenApiParameter('event_type', OpenApiTypes.STR, description='Filter by event type'),
            OpenApiParameter('status', OpenApiTypes.STR, description='Filter by status'),
            OpenApiParameter('start_date', OpenApiTypes.DATE, description='Filter events from this date'),
            OpenApiParameter('end_date', OpenApiTypes.DATE, description='Filter events until this date'),
            OpenApiParameter('upcoming', OpenApiTypes.BOOL, description='Show only upcoming events'),
        ]
    )
    def list(self, request, *args, **kwargs):
        """List all events for the organization"""
        return super().list(request, *args, **kwargs)
    
    def create(self, request, *args, **kwargs):
        """Create a new event (admin/attendance officer only)"""
        permission_error = self.check_admin_permission()
        if permission_error:
            return permission_error
        return super().create(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """Update an event (admin/attendance officer only)"""
        permission_error = self.check_admin_permission()
        if permission_error:
            return permission_error
        return super().update(request, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        """Partially update an event (admin/attendance officer only)"""
        permission_error = self.check_admin_permission()
        if permission_error:
            return permission_error
        return super().partial_update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Delete an event (admin/attendance officer only)"""
        permission_error = self.check_admin_permission()
        if permission_error:
            return permission_error
        return super().destroy(request, *args, **kwargs)
    
    @extend_schema(
        responses={200: EventAttendanceSerializer(many=True)},
        description="Get attendance list for an event"
    )
    @action(detail=True, methods=['get'])
    def attendance(self, request, pk=None):
        """Get attendance for a specific event"""
        event = self.get_object()
        attendances = EventAttendance.objects.filter(event=event).select_related('user', 'marked_by')
        serializer = EventAttendanceSerializer(attendances, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        request=MarkAttendanceSerializer,
        responses={200: EventAttendanceSerializer},
        description="Mark attendance for a single user"
    )
    @action(detail=True, methods=['post'])
    def mark_attendance(self, request, pk=None):
        """Mark attendance for a single user"""
        permission_error = self.check_admin_permission()
        if permission_error:
            return permission_error
        
        event = self.get_object()
        serializer = MarkAttendanceSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        user = User.objects.get(id=serializer.validated_data['user_id'])
        
        # Create or update attendance record
        attendance, created = EventAttendance.objects.update_or_create(
            event=event,
            user=user,
            defaults={
                'status': serializer.validated_data['status'],
                'notes': serializer.validated_data.get('notes', ''),
                'marked_by': request.user,
                'marked_at': timezone.now()
            }
        )
        
        return Response(EventAttendanceSerializer(attendance).data)
    
    @extend_schema(
        request=BulkAttendanceSerializer,
        responses={200: OpenApiTypes.OBJECT},
        description="Mark attendance for multiple users at once"
    )
    @action(detail=True, methods=['post'])
    def bulk_mark_attendance(self, request, pk=None):
        """Mark attendance for multiple users at once"""
        permission_error = self.check_admin_permission()
        if permission_error:
            return permission_error
        
        event = self.get_object()
        serializer = BulkAttendanceSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        created_count = 0
        updated_count = 0
        
        for item in serializer.validated_data['attendances']:
            user = User.objects.get(id=item['user_id'])
            attendance, created = EventAttendance.objects.update_or_create(
                event=event,
                user=user,
                defaults={
                    'status': item['status'],
                    'notes': item.get('notes', ''),
                    'marked_by': request.user,
                    'marked_at': timezone.now()
                }
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
        
        return Response({
            'message': 'Attendance marked successfully',
            'created': created_count,
            'updated': updated_count,
            'total': created_count + updated_count
        })
    
    @extend_schema(
        responses={200: OpenApiTypes.OBJECT},
        description="Get list of eligible members for this event"
    )
    @action(detail=True, methods=['get'])
    def eligible_members(self, request, pk=None):
        """Get list of members who should attend this event"""
        event = self.get_object()
        members = event.get_eligible_members()
        
        # Get existing attendance records
        existing_attendance = EventAttendance.objects.filter(event=event).values_list('user_id', flat=True)
        
        result = []
        for member in members:
            result.append({
                'id': str(member.id),
                'email': member.email,
                'name': f"{member.first_name} {member.last_name}".strip() or member.email,
                'voice_part': member.member_part,
                'has_attendance': member.id in existing_attendance
            })
        
        return Response({
            'count': len(result),
            'members': result
        })


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

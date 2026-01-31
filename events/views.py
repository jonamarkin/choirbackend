from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from events.models import Event
from events.serializers import (
    EventSerializer, EventListSerializer, EventCreateSerializer, RecurringEventSerializer
)
from attendance.models import EventAttendance
from attendance.serializers import (
    EventAttendanceSerializer, MarkAttendanceSerializer, BulkAttendanceSerializer
)
from authentication.models import User


class CanManageEvents:
    """Permission for full event management (Create/Edit/Delete)"""
    @staticmethod
    def has_permission(user):
        return (
            user.is_superuser or
            user.role in ['super_admin', 'admin', 'attendance_officer']
        )

class CanMarkAttendance:
    """Permission for marking attendance (includes Part Leaders)"""
    @staticmethod
    def has_permission(user):
        return (
            user.is_superuser or
            user.role in ['super_admin', 'admin', 'attendance_officer', 'part_leader']
        )


@extend_schema(tags=['Events'])
class EventViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing choir events.
    
    Actions:
    - list: Get all events for the organization (All members)
    - retrieve: Get single event details (All members)
    - create: Create new event (Admin/Attendance Officer)
    - update: Update event (Admin/Attendance Officer)
    - destroy: Delete event (Admin/Attendance Officer)
    - mark_attendance: Mark attendance (Admin/Officer/Part Leader)
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
        if self.action == 'create_recurring':
            return RecurringEventSerializer
        return EventSerializer
    
    def check_event_management_permission(self):
        """Check if user can manage events (create/edit/delete)"""
        if not CanManageEvents.has_permission(self.request.user):
            return Response(
                {'error': 'You do not have permission to perform this action'},
                status=status.HTTP_403_FORBIDDEN
            )
        return None
    
    def check_attendance_marking_permission(self):
        """Check if user can mark attendance"""
        if not CanMarkAttendance.has_permission(self.request.user):
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
        permission_error = self.check_event_management_permission()
        if permission_error:
            return permission_error
        return super().create(request, *args, **kwargs)
        
    @extend_schema(
        request=RecurringEventSerializer,
        responses={201: OpenApiTypes.OBJECT},
        description="Create multiple recurring events (e.g., Weekly)"
    )
    @action(detail=False, methods=['post'], url_path='recurring')
    def create_recurring(self, request):
        """Create a recurring series of events"""
        permission_error = self.check_event_management_permission()
        if permission_error:
            return permission_error
            
        serializer = RecurringEventSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        base_data = data['base_event']
        frequency = data['frequency']
        count = data.get('count')
        until_date = data.get('until_date')
        
        # Calculate recurrence delta
        if frequency == 'daily':
            delta = timedelta(days=1)
        elif frequency == 'weekly':
            delta = timedelta(weeks=1)
        elif frequency == 'biweekly':
            delta = timedelta(weeks=2)
        else:
            delta = timedelta(weeks=1)
            
        events_created = []
        current_start = base_data['start_datetime']
        current_end = base_data.get('end_datetime')
        duration = current_end - current_start if current_end else None
        
        # Determine number of events
        if count:
            limit = count
        else:
            # Safely estimate loops to avoid infinite
            limit = 52 # Max 1 year for weekly
            
        # Loop
        created_count = 0
        while True:
            # Stop conditions
            if count and created_count >= count:
                break
            if until_date and current_start.date() > until_date:
                break
            if created_count >= 100: # Hard safety limit
                break
                
            # Create Event
            event = Event.objects.create(
                organization=request.user.organization,
                created_by=request.user,
                title=base_data['title'],
                description=base_data.get('description', ''),
                event_type=base_data['event_type'],
                location=base_data.get('location', ''),
                start_datetime=current_start,
                end_datetime=current_end,
                is_mandatory=base_data.get('is_mandatory', True),
                target_voice_parts=base_data.get('target_voice_parts'),
                status=base_data.get('status', 'scheduled')
            )
            events_created.append(event.id)
            created_count += 1
            
            # Increment
            current_start += delta
            if current_end:
                 current_end += delta
                 
        return Response({
            'message': f"Successfully created {created_count} events.",
            'event_ids': events_created
        }, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """Update an event (admin/attendance officer only)"""
        permission_error = self.check_event_management_permission()
        if permission_error:
            return permission_error
        return super().update(request, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        """Partially update an event (admin/attendance officer only)"""
        permission_error = self.check_event_management_permission()
        if permission_error:
            return permission_error
        return super().partial_update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Delete an event (admin/attendance officer only)"""
        permission_error = self.check_event_management_permission()
        if permission_error:
            return permission_error
        return super().destroy(request, *args, **kwargs)
    
    @extend_schema(
        responses={200: EventAttendanceSerializer(many=True)},
        description="Get attendance list for an event"
    )
    @action(detail=True, methods=['get'])
    def attendance(self, request, slug=None):
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
    def mark_attendance(self, request, slug=None):
        """Mark attendance for a single user"""
        permission_error = self.check_attendance_marking_permission()
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
    def bulk_mark_attendance(self, request, slug=None):
        """Mark attendance for multiple users at once"""
        permission_error = self.check_attendance_marking_permission()
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
    def eligible_members(self, request, slug=None):
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

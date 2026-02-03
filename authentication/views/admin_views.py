from django.db.models import Q
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import get_user_model

from authentication.permissions import IsOrganizationAdmin
from authentication.serializers.admin_serializers import (
    AdminUserListSerializer,
    AdminUserDetailSerializer,
    AdminUserUpdateSerializer
)

User = get_user_model()


class UserFilter(filters.FilterSet):
    """Filter for user listing"""
    search = filters.CharFilter(method='filter_search')
    is_approved = filters.BooleanFilter()
    is_active = filters.BooleanFilter()
    role = filters.ChoiceFilter(choices=User.ROLE_CHOICES)
    member_part = filters.ChoiceFilter(choices=User.MEMBER_PART_CHOICES)

    class Meta:
        model = User
        fields = ['is_approved', 'is_active', 'role', 'member_part']

    def filter_search(self, queryset, name, value):
        """Search by name, email, or phone"""
        return queryset.filter(
            Q(first_name__icontains=value) |
            Q(last_name__icontains=value) |
            Q(email__icontains=value) |
            Q(phone_number__icontains=value)
        )


@extend_schema(tags=['Admin - Users'])
class AdminUserViewSet(viewsets.ModelViewSet):
    """
    Admin endpoints for managing users within an organization.
    
    Only accessible by users with 'super_admin' or 'admin' role.
    """
    permission_classes = [IsAuthenticated, IsOrganizationAdmin]
    parser_classes = [JSONParser]
    filterset_class = UserFilter
    search_fields = ['first_name', 'last_name', 'email', 'phone_number']
    ordering_fields = ['created_at', 'last_name', 'email']
    ordering = ['-created_at']

    def get_queryset(self):
        """Return users in the same organization as the requesting admin"""
        user = self.request.user
        # System admins can see all users
        if user.is_superuser:
            return User.objects.all().select_related('organization')
        # Organization admins see only their org's users
        if user.organization:
            return User.objects.filter(
                organization=user.organization
            ).select_related('organization')
        return User.objects.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return AdminUserListSerializer
        if self.action in ['update', 'partial_update']:
            return AdminUserUpdateSerializer
        return AdminUserDetailSerializer

    @extend_schema(
        summary="List Users",
        description="List all users in the organization with optional filters.",
        parameters=[
            OpenApiParameter(name='search', description='Search by name, email, or phone'),
            OpenApiParameter(name='is_approved', description='Filter by approval status', type=bool),
            OpenApiParameter(name='is_active', description='Filter by active status', type=bool),
            OpenApiParameter(name='role', description='Filter by role'),
            OpenApiParameter(name='member_part', description='Filter by voice part'),
        ],
        responses={200: AdminUserListSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Get User Details",
        description="Get detailed information about a specific user.",
        responses={200: AdminUserDetailSerializer},
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Update User",
        description="Update user details (role, member_part, etc.).",
        request=AdminUserUpdateSerializer,
        responses={200: AdminUserDetailSerializer},
    )
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AdminUserDetailSerializer(instance).data)

    @extend_schema(
        summary="Approve User",
        description="Approve a pending user to allow them full access.",
        responses={200: {'example': {'message': 'User approved successfully', 'user': {}}}},
    )
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        user = self.get_object()
        if user.is_approved:
            return Response(
                {'message': 'User is already approved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        user.is_approved = True
        user.save(update_fields=['is_approved', 'updated_at'])
        return Response({
            'message': 'User approved successfully',
            'user': AdminUserListSerializer(user).data
        })

    @extend_schema(
        summary="Activate User",
        description="Activate a deactivated user account.",
        responses={200: {'example': {'message': 'User activated successfully', 'user': {}}}},
    )
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        user = self.get_object()
        if user.is_active:
            return Response(
                {'message': 'User is already active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        user.is_active = True
        user.save(update_fields=['is_active', 'updated_at'])
        return Response({
            'message': 'User activated successfully',
            'user': AdminUserListSerializer(user).data
        })

    @extend_schema(
        summary="Deactivate User",
        description="Deactivate a user account (prevents login).",
        responses={200: {'example': {'message': 'User deactivated successfully', 'user': {}}}},
    )
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        user = self.get_object()
        if user == request.user:
            return Response(
                {'error': 'You cannot deactivate your own account'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not user.is_active:
            return Response(
                {'message': 'User is already inactive'},
                status=status.HTTP_400_BAD_REQUEST
            )
        user.is_active = False
        user.save(update_fields=['is_active', 'updated_at'])
        return Response({
            'message': 'User deactivated successfully',
            'user': AdminUserListSerializer(user).data
        })

    # Disable create and delete - users are created via registration
    def create(self, request, *args, **kwargs):
        return Response(
            {'error': 'Users are created via registration, not this endpoint'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {'error': 'User deletion is not allowed via this endpoint'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

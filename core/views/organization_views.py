from drf_spectacular.utils import extend_schema
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from authentication.models import User
from authentication.serializers.user_serializers import UserSerializer, OrganizationUserSerializer
from core.models import Organization
from core.serializers.organization_serializers import OrganizationSerializer, CreateOrganizationSerializer, \
    AddOrganizationMemberSerializer


@extend_schema(tags=['Organization'])
class OrganizationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, ]
    parser_classes = [JSONParser]
    serializer_class = OrganizationSerializer

    def get_queryset(self):
        return Organization.objects.all()

    @extend_schema(
        summary="Get Organization Details",
        description="Get organization details including name, address, and contact information.",
        responses={200: OrganizationSerializer},
    )
    def list(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_system_admin():
            return super().list(request)
        return Response(status=status.HTTP_403_FORBIDDEN, data={'error': 'Permission denied.'})

    @extend_schema(
        summary="Get Organization Details",
        description="Get organization details including name, address, and contact information.",
        responses={200: OrganizationSerializer},
    )
    def retrieve(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_system_admin():
            return super().retrieve(request, *args, **kwargs)
        return Response(status=status.HTTP_403_FORBIDDEN, data={'error': 'Permission denied.'})

    @extend_schema(
        summary="Update Organization Details",
        description="Update organization details including name, address, and contact information.",
        responses={200: OrganizationSerializer},
    )
    def update(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_system_admin():
            return super().update(request, *args, **kwargs)
        return Response(status=status.HTTP_403_FORBIDDEN, data={'error': 'Permission denied.'})

    @extend_schema(
        summary="Create Organization",
        description="Create organization.",
        responses={201: OrganizationSerializer},
    )
    def create(self, request, *args, **kwargs):
        if not request.user.is_system_admin():
            return Response(status=status.HTTP_403_FORBIDDEN, data={'error': 'Permission denied.'})

        serializer = CreateOrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Delete Organization",
        description="Delete organization.",
        responses={204: None},
        deprecated=True
    )
    def destroy(self, request, *args, **kwargs):
        # if not request.user.is_system_admin():
        #     return Response(status=status.HTTP_403_FORBIDDEN, data={'error': 'Permission denied.'})
        # return super().destroy(request, *args, **kwargs)
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED, data={'error': 'Method not allowed.'})

    def partial_update(self, request, *args, **kwargs):
        if not request.user.is_system_admin():
            return Response(status=status.HTTP_403_FORBIDDEN, data={'error': 'Permission denied.'})
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Get Organization Member",
        description="Get organization member.",
        responses={200: OrganizationUserSerializer(many=True)},
    )
    @action(methods=['get'], detail=True)
    def members(self, request, pk=None):
        if not request.user.is_system_admin():
            return Response(status=status.HTTP_403_FORBIDDEN, data={'error': 'Permission denied.'})
        return Response(OrganizationUserSerializer(self.get_object().users.all(), many=True).data)

    @extend_schema(
        summary="Add Organization Member",
        description="Add organization member. This can only be done by system admins or super admin of organization.",
        responses={201: None},
        request=AddOrganizationMemberSerializer()
    )
    @action(methods=['post'], detail=True)
    def add_member(self, request):
        organization = self.get_object()
        if (not request.user.is_system_admin()) or (
                request.user.organization == organization and not request.user.is_super_admin()):
            return Response(status=status.HTTP_403_FORBIDDEN, data={'error': 'Permission denied.'})

        user_to_add_email = AddOrganizationMemberSerializer(data=request.data)
        user_to_add_email.is_valid(raise_exception=True)

        user = User.objects.get(email=user_to_add_email.validated_data['email'])
        if user.organization:
            return Response(status=status.HTTP_400_BAD_REQUEST,
                            data={'error': 'User already belongs to an organization.'})
        user.organization = organization
        user.save()

        return Response(status=status.HTTP_201_CREATED, data={'message': 'User added successfully.'})

    @extend_schema(
        summary="Remove Organization Member",
        description="Remove organization member. This can only be done by system admins or super admin of organization.",
        responses={201: None},
        request=AddOrganizationMemberSerializer()
    )
    @action(methods=['post'], detail=True)
    def remove_member(self, request):
        organization = self.get_object()
        if (not request.user.is_system_admin()) or (
                request.user.organization == organization and not request.user.is_super_admin()):
            return Response(status=status.HTTP_403_FORBIDDEN, data={'error': 'Permission denied.'})

        user_to_remove_email = AddOrganizationMemberSerializer(data=request.data)
        user_to_remove_email.is_valid(raise_exception=True)

        user = User.objects.get(email=user_to_remove_email.validated_data['email'])
        if user == request.user:
            return Response(status=status.HTTP_400_BAD_REQUEST,
                            data={'error': 'Cannot remove yourself from organization.'})
        if user.organization is None:
            return Response(status=status.HTTP_400_BAD_REQUEST,
                            data={'error': 'User doesn\'t belong to an organization.'})
        if user.organization != organization:
            return Response(status=status.HTTP_400_BAD_REQUEST,
                            data={'error': 'User doesn\'t belong to this organization.'})
        user.organization = None
        user.save()

        return Response(status=status.HTTP_200_OK, data={'message': 'User removed successfully.'})

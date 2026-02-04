from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from authentication.models import User
from core.models import ContactGroup, Contact
from core.serializers.contact_serializers import (
    ContactGroupSerializer,
    ContactGroupDetailSerializer,
    ContactSerializer,
    AddContactsToGroupSerializer,
    RemoveContactsFromGroupSerializer,
    BulkCreateContactsSerializer,
    MemberPhoneSerializer,
)


@extend_schema(tags=['Contact Groups'])
class ContactGroupViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing contact groups.
    Groups are organization-scoped for multi-tenancy.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ContactGroupSerializer

    def get_queryset(self):
        """Filter groups by user's organization."""
        if not self.request.user.organization:
            return ContactGroup.objects.none()
        return ContactGroup.objects.filter(organization=self.request.user.organization)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ContactGroupDetailSerializer
        return ContactGroupSerializer

    @extend_schema(
        summary="List Contact Groups",
        description="Get all contact groups for the user's organization.",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Create Contact Group",
        description="Create a new contact group.",
    )
    def create(self, request, *args, **kwargs):
        if not request.user.organization:
            return Response(
                {'error': 'User must belong to an organization'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Get Contact Group Details",
        description="Get detailed information about a contact group including its contacts.",
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Add Contacts to Group",
        description="Add existing contacts to a group.",
        request=AddContactsToGroupSerializer,
    )
    @action(detail=True, methods=['post'], url_path='add-contacts')
    def add_contacts(self, request, pk=None):
        group = self.get_object()
        serializer = AddContactsToGroupSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        contact_ids = serializer.validated_data['contact_ids']
        contacts = Contact.objects.filter(
            id__in=contact_ids,
            organization=request.user.organization
        )
        
        group.contacts.add(*contacts)
        
        return Response({
            'message': f'Added {contacts.count()} contacts to group',
            'added_count': contacts.count()
        })

    @extend_schema(
        summary="Remove Contacts from Group",
        description="Remove contacts from a group.",
        request=RemoveContactsFromGroupSerializer,
    )
    @action(detail=True, methods=['post'], url_path='remove-contacts')
    def remove_contacts(self, request, pk=None):
        group = self.get_object()
        serializer = RemoveContactsFromGroupSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        contact_ids = serializer.validated_data['contact_ids']
        contacts = Contact.objects.filter(id__in=contact_ids)
        
        group.contacts.remove(*contacts)
        
        return Response({
            'message': f'Removed {contacts.count()} contacts from group',
            'removed_count': contacts.count()
        })

    @extend_schema(
        summary="Get Group Contacts",
        description="Get all contacts in a group.",
        responses={200: ContactSerializer(many=True)}
    )
    @action(detail=True, methods=['get'], url_path='contacts')
    def get_contacts(self, request, pk=None):
        group = self.get_object()
        contacts = group.contacts.all()
        serializer = ContactSerializer(contacts, many=True)
        return Response(serializer.data)


@extend_schema(tags=['Contacts'])
class ContactViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing individual contacts.
    Contacts are organization-scoped for multi-tenancy.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ContactSerializer

    def get_queryset(self):
        """Filter contacts by user's organization."""
        if not self.request.user.organization:
            return Contact.objects.none()
        return Contact.objects.filter(organization=self.request.user.organization)

    @extend_schema(
        summary="List Contacts",
        description="Get all contacts for the user's organization.",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Create Contact",
        description="Create a new contact.",
    )
    def create(self, request, *args, **kwargs):
        if not request.user.organization:
            return Response(
                {'error': 'User must belong to an organization'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Bulk Create Contacts",
        description="Create multiple contacts at once, optionally adding them to a group.",
        request=BulkCreateContactsSerializer,
    )
    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        if not request.user.organization:
            return Response(
                {'error': 'User must belong to an organization'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = BulkCreateContactsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        contacts_data = serializer.validated_data['contacts']
        group_id = serializer.validated_data.get('group_id')
        
        created_contacts = []
        for contact_data in contacts_data:
            contact = Contact.objects.create(
                organization=request.user.organization,
                name=contact_data['name'],
                phone_number=contact_data['phone_number']
            )
            created_contacts.append(contact)
        
        # Add to group if specified
        if group_id:
            try:
                group = ContactGroup.objects.get(
                    id=group_id,
                    organization=request.user.organization
                )
                for contact in created_contacts:
                    contact.groups.add(group)
            except ContactGroup.DoesNotExist:
                pass  # Ignore if group doesn't exist
        
        return Response({
            'message': f'Created {len(created_contacts)} contacts',
            'created_count': len(created_contacts),
            'contacts': ContactSerializer(created_contacts, many=True).data
        }, status=status.HTTP_201_CREATED)


@extend_schema(tags=['SMS'])
class MemberPhoneViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for fetching choir members with phone numbers.
    Useful for selecting SMS recipients from organization members.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = MemberPhoneSerializer

    def get_queryset(self):
        """Filter members by user's organization who have phone numbers."""
        if not self.request.user.organization:
            return User.objects.none()
        return User.objects.filter(
            organization=self.request.user.organization,
            phone_number__isnull=False,
            is_active=True
        ).exclude(phone_number='')

    @extend_schema(
        summary="List Members with Phone Numbers",
        description="Get all organization members who have phone numbers for SMS sending.",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Get Member Phones by Part",
        description="Get members filtered by voice part (soprano, alto, tenor, bass, etc.).",
    )
    @action(detail=False, methods=['get'], url_path='by-part/(?P<part>[^/.]+)')
    def by_part(self, request, part=None):
        queryset = self.get_queryset().filter(member_part=part)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Get Member Phones by Role",
        description="Get members filtered by role.",
    )
    @action(detail=False, methods=['get'], url_path='by-role/(?P<role>[^/.]+)')
    def by_role(self, request, role=None):
        queryset = self.get_queryset().filter(role=role)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

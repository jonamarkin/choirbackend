from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from subscriptions.models import DirectDebit
from subscriptions.serializers.direct_debit_serializers import (
    DirectDebitListSerializer,
    DirectDebitResponseSerializer,
    DirectDebitUpdateSerializer,
)


@extend_schema(tags=['Direct Debit'])
class DirectDebitViewSet(viewsets.ModelViewSet):
    serializer_class = DirectDebitResponseSerializer

    def get_permissions(self):
        if self.action == 'webhook':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'list':
            return DirectDebitListSerializer
        if self.action == 'partial_update':
            return DirectDebitUpdateSerializer
        return DirectDebitResponseSerializer

    def get_queryset(self):
        if self.request.user.is_authenticated:
            if self.request.user.is_system_admin():
                return DirectDebit.objects.all()
            return DirectDebit.objects.filter(user=self.request.user)
        return DirectDebit.objects.none()

    # @extend_schema(
    #     summary="Webhook",
    #     description="Receive webhook notifications from the payment gateway.",
    # )
    # def webhook(self, request):
    #     pass

    @extend_schema(
        summary="Get Direct Debits",
        description="Retrieve a list of direct debits for the authenticated user.",
        responses={
            200: DirectDebitListSerializer(many=True),
        }
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Get Direct Debit",
        description="Retrieve a direct debit by ID.",
        responses={
            200: DirectDebitResponseSerializer(),
        }
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Disabled — use the registration flow",
        description="Direct creation is disabled. Register a direct debit via the Hubtel registration flow.",
    )
    def create(self, request, *args, **kwargs):
        return Response(
            {'error': 'Use the direct-debit registration flow to create direct debits.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @extend_schema(
        summary="Disabled — use PATCH to edit the amount",
        description="Full replacement is not supported; use PATCH to edit the amount only.",
    )
    def update(self, request, *args, **kwargs):
        return Response(
            {'error': 'Full update is not supported; use PATCH to edit the amount.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @extend_schema(
        summary="Update amount",
        description="Edit the debit amount of a direct debit. Only the amount can be changed.",
        request=DirectDebitUpdateSerializer,
        responses={200: DirectDebitResponseSerializer},
    )
    def partial_update(self, request, *args, **kwargs):
        direct_debit = self.get_object()
        serializer = self.get_serializer(direct_debit, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(DirectDebitResponseSerializer(direct_debit).data)

    @extend_schema(
        summary="Delete direct debit",
        description="Delete a direct debit owned by the authenticated user.",
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

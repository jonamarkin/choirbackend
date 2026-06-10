import logging

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from subscriptions.models import DirectDebit
from subscriptions.serializers import DirectDebitChargeWebhookSerializer
from subscriptions.serializers.direct_debit_serializers import (
    DirectDebitListSerializer,
    DirectDebitOtpVerificationRequestSerializer,
    DirectDebitPreapprovalWebhookSerializer,
    DirectDebitResponseSerializer,
    DirectDebitUpdateSerializer,
    RegisterDirectDebitRequestSerializer,
)
from subscriptions.services.hubtel_service import HubtelPaymentService

logger = logging.getLogger(__name__)


@extend_schema(tags=['Direct Debit'])
class DirectDebitViewSet(viewsets.ModelViewSet):
    serializer_class = DirectDebitResponseSerializer

    def get_permissions(self):
        if self.action in ('charge_webhook', 'preapproval_webhook'):
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
        description="Deactivate a direct debit owned by the authenticated user.",
    )
    def destroy(self, request, *args, **kwargs):
        direct_debit = self.get_object()
        direct_debit.deactivate()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Register a direct debit",
        description="Start the Hubtel preapproval registration for a verified wallet and a "
                    "subscription the user is enrolled in. Returns the created mandate and the "
                    "verification type (e.g. OTP) needed to complete it.",
        request=RegisterDirectDebitRequestSerializer,
        responses={201: DirectDebitResponseSerializer},
    )
    @action(detail=False, methods=['post'])
    def register(self, request):
        serializer = RegisterDirectDebitRequestSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        wallet = serializer.validated_data['wallet_id']
        user_subscription = serializer.validated_data['subscription_id']

        try:
            direct_debit, verification_type = HubtelPaymentService().initiate_hubtel_direct_debit_registration(
                wallet_id=wallet.id,
                user_subscription_id=user_subscription.id,
                amount=serializer.validated_data['amount'],
                period_type=serializer.validated_data['period_type'],
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if direct_debit is None:
            return Response(
                {'error': 'Failed to initiate direct debit registration with Hubtel.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        data = DirectDebitResponseSerializer(direct_debit).data
        data['verification_type'] = verification_type
        return Response(data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Verify direct debit OTP",
        description="Verify the OTP for a pending direct-debit registration. On success the "
                    "mandate stays pending until Hubtel's preapproval callback approves it.",
        request=DirectDebitOtpVerificationRequestSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
    )
    @action(detail=True, methods=['post'], url_path='verify-otp')
    def verify_otp(self, request, pk=None):
        direct_debit = self.get_object()
        serializer = DirectDebitOtpVerificationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        verified = HubtelPaymentService().verify_hubtel_direct_debit_otp(
            otp_code=serializer.validated_data['otp'],
            direct_debit_id=direct_debit.id,
        )
        if not verified:
            return Response(
                {'verified': False, 'error': 'OTP verification failed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {'verified': True, 'message': 'OTP verified. Awaiting preapproval confirmation.'},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Check preapproval status",
        description="Query Hubtel for the mandate's preapproval status and approve it locally "
                    "if Hubtel reports APPROVED. Fallback for when the preapproval callback is delayed.",
        responses={200: DirectDebitResponseSerializer},
    )
    @action(detail=True, methods=['get'], url_path='status')
    def preapproval_status(self, request, pk=None):
        direct_debit = self.get_object()
        HubtelPaymentService().check_hubtel_direct_debit_preapproval_status(direct_debit.id)
        direct_debit.refresh_from_db()
        return Response(DirectDebitResponseSerializer(direct_debit).data)

    @extend_schema(
        summary="Direct Debit Charge Webhook",
        description="Receive the asynchronous charge result from Hubtel for a direct-debit "
                    "charge. IP-restricted, no authentication. Hubtel calls this after a charge "
                    "reaches its final state.",
        request=DirectDebitChargeWebhookSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            500: OpenApiTypes.OBJECT,
        },
    )
    @method_decorator(csrf_exempt, name='dispatch')
    @action(detail=False, methods=['post'], url_path='charge-webhook')
    def charge_webhook(self, request):
        logger.info("Direct debit charge webhook data from Hubtel: %s", request.data)

        hubtel_service = HubtelPaymentService()
        if not hubtel_service.validate_callback_ip(request):
            return Response({'error': 'Invalid IP address'}, status=status.HTTP_403_FORBIDDEN)

        serializer = DirectDebitChargeWebhookSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid webhook data', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            success, message, _ = hubtel_service.handle_direct_debit_charge_callback(
                callback_data=serializer.validated_data,
            )
            return Response(
                {'status': 'success' if success else 'failed', 'message': message},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Direct debit charge webhook error: {e}", exc_info=True)
            return Response(
                {'error': 'Webhook processing error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Direct Debit Preapproval Webhook",
        description="Receive Hubtel's asynchronous preapproval (registration) result. "
                    "IP-restricted, no authentication. Marks the mandate approved when "
                    "Hubtel reports APPROVED.",
        request=DirectDebitPreapprovalWebhookSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            500: OpenApiTypes.OBJECT,
        },
    )
    @method_decorator(csrf_exempt, name='dispatch')
    @action(detail=False, methods=['post'], url_path='preapproval-webhook')
    def preapproval_webhook(self, request):
        logger.info("Direct debit preapproval webhook data from Hubtel: %s", request.data)

        hubtel_service = HubtelPaymentService()
        if not hubtel_service.validate_callback_ip(request):
            return Response({'error': 'Invalid IP address'}, status=status.HTTP_403_FORBIDDEN)

        serializer = DirectDebitPreapprovalWebhookSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid webhook data', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            success, message, _ = hubtel_service.handle_direct_debit_preapproval_callback(
                callback_data=serializer.validated_data,
            )
            return Response(
                {'status': 'success' if success else 'failed', 'message': message},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Direct debit preapproval webhook error: {e}", exc_info=True)
            return Response(
                {'error': 'Webhook processing error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

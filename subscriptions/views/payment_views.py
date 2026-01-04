"""
Payment Views
Handles all payment-related API endpoints using Hubtel integration.
"""
import logging

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from subscriptions.models import PaymentTransaction, UserSubscription
from subscriptions.serializers import (
    PaymentTransactionSerializer,
    PaymentInitiateSerializer,
    PaymentInitiateResponseSerializer,
    PaymentWebhookSerializer,
    PaymentStatusSerializer,
)
from subscriptions.services.hubtel_service import HubtelPaymentService

logger = logging.getLogger(__name__)


class PaymentViewSet(viewsets.ViewSet):
    """
    ViewSet for handling Hubtel payment operations.

    Actions:
    - initiate: Start a new payment (authenticated)
    - webhook: Receive Hubtel callbacks (no auth, IP-restricted)
    - status: Check payment status (authenticated)
    - list: Get user's payment history (authenticated)
    - retrieve: Get specific payment details (authenticated)
    - verify: Manually verify payment with Hubtel API (authenticated, admin only)
    """

    def get_permissions(self):
        """
        Return appropriate permissions based on action.
        """
        if self.action == 'webhook':
            # Webhook endpoint is public but IP-restricted
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """Get queryset filtered by current user"""
        if self.request.user.is_authenticated:
            # Users can only see their own payments
            # Admins can see all payments in their organization
            if hasattr(self.request.user, 'is_executive') and self.request.user.is_executive():
                return PaymentTransaction.objects.filter(
                    organization=self.request.user.organization
                )
            return PaymentTransaction.objects.filter(user=self.request.user)
        return PaymentTransaction.objects.none()

    @extend_schema(
        summary="Initiate Payment",
        description="Initiate a payment for a user subscription using Hubtel Online Checkout. Returns a checkout URL to redirect the user to Hubtel's hosted payment page.",
        request=PaymentInitiateSerializer,
        responses={
            201: PaymentInitiateResponseSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
            500: OpenApiTypes.OBJECT,
        },
        tags=['Payments'],
    )
    @action(detail=False, methods=['post'])
    def initiate(self, request):
        """
        Initiate a payment for a user subscription.

        POST /api/v1/subscriptions/payments/initiate/
        {
            "user_subscription_id": "uuid",
            "amount": "50.00",  // Optional, defaults to outstanding amount
            "metadata": {}      // Optional
        }

        Returns:
        {
            "transaction_id": "uuid",
            "client_reference": "PAY-xxx",
            "checkout_url": "https://pay.hubtel.com/...",
            "amount": "50.00",
            "currency": "GHS",
            "expires_at": "2024-01-01T12:05:00Z",
            "description": "..."
        }
        """
        serializer = PaymentInitiateSerializer(data=request.data, context={'request': request})

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        validated_data = serializer.validated_data
        user_subscription_id = validated_data['user_subscription_id']
        amount = validated_data.get('amount')
        metadata = validated_data.get('metadata', {})

        # Add request metadata
        metadata.update({
            'ip_address': request.META.get('REMOTE_ADDR', ''),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        })

        try:
            # Get user subscription
            user_subscription = UserSubscription.objects.get(id=user_subscription_id)

            # Initiate payment using Hubtel service
            hubtel_service = HubtelPaymentService()
            transaction = hubtel_service.initiate_payment(
                user_subscription=user_subscription,
                amount=amount,
                metadata=metadata
            )

            print(f"This is the transaction: {transaction}")

            # Prepare response
            response_serializer = PaymentInitiateResponseSerializer({
                'transaction_id': transaction.id,
                'client_reference': transaction.client_reference,
                'checkout_url': transaction.checkout_url,
                'amount': transaction.amount,
                'currency': transaction.currency,
                'expires_at': transaction.expires_at,
                'description': transaction.description,
            })

            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )

        except UserSubscription.DoesNotExist:
            return Response(
                {'error': 'User subscription not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Payment initiation error: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to initiate payment. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Hubtel Payment Webhook",
        description="Receive payment notifications from Hubtel. This endpoint is IP-restricted and does not require authentication. Called automatically by Hubtel after payment completion.",
        request=PaymentWebhookSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            500: OpenApiTypes.OBJECT,
        },
        tags=['Payments', 'Webhooks'],
    )
    @method_decorator(csrf_exempt, name='dispatch')
    @action(detail=False, methods=['post'])
    def webhook(self, request):
        """
        Receive payment notifications from Hubtel.

        POST /api/v1/subscriptions/payments/webhook/

        Validates:
        - IP whitelist
        - Request data structure
        - Duplicate prevention

        Updates PaymentTransaction status and UserSubscription accordingly.
        """
        # Log webhook attempt
        logger.info(f"Webhook received from IP: {request.META.get('REMOTE_ADDR')}")

        # Validate callback data structure
        serializer = PaymentWebhookSerializer(data=request.data)

        if not serializer.is_valid():
            logger.warning(f"Invalid webhook data: {serializer.errors}")
            return Response(
                {'error': 'Invalid webhook data', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Process callback using Hubtel service
            hubtel_service = HubtelPaymentService()
            success, message, transaction = hubtel_service.handle_callback(
                callback_data=serializer.validated_data,
                request=request
            )

            if success:
                logger.info(f"Webhook processed successfully: {message}")
                return Response(
                    {'status': 'success', 'message': message},
                    status=status.HTTP_200_OK
                )
            else:
                logger.warning(f"Webhook processing failed: {message}")
                return Response(
                    {'status': 'failed', 'message': message},
                    status=status.HTTP_200_OK  # Return 200 to prevent retries
                )

        except Exception as e:
            logger.error(f"Webhook processing error: {e}", exc_info=True)
            return Response(
                {'error': 'Webhook processing error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Check Payment Status",
        description="Get current status of a payment transaction. If payment is still pending, optionally queries Hubtel API for the latest status.",
        responses={
            200: PaymentStatusSerializer,
            404: OpenApiTypes.OBJECT,
        },
        tags=['Payments'],
    )
    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """
        Check current status of a payment.

        GET /api/v1/subscriptions/payments/{id}/status/

        Returns current status from database and optionally
        queries Hubtel API for latest status if payment is pending.
        """
        try:
            transaction = self.get_queryset().get(pk=pk)
        except PaymentTransaction.DoesNotExist:
            return Response(
                {'error': 'Payment transaction not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # If payment is pending and not expired, check with Hubtel
        if transaction.status in ['initiated', 'pending'] and not transaction.is_expired():
            try:
                hubtel_service = HubtelPaymentService()
                transaction = hubtel_service.check_payment_status(transaction)
            except Exception as e:
                logger.error(f"Status check error: {e}", exc_info=True)
                # Continue with current status from database

        # Prepare response
        response_serializer = PaymentStatusSerializer({
            'transaction_id': transaction.id,
            'client_reference': transaction.client_reference,
            'status': transaction.status,
            'amount': transaction.amount,
            'currency': transaction.currency,
            'payment_channel': transaction.payment_channel or '',
            'payment_type': transaction.payment_type or '',
            'confirmed_at': transaction.confirmed_at,
            'error_message': transaction.error_message or '',
        })

        return Response(response_serializer.data)

    @extend_schema(
        summary="List Payment Transactions",
        description="List user's payment transactions with optional filtering by status and subscription.",
        parameters=[
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by transaction status: initiated, pending, success, failed, expired, cancelled, refunded',
                required=False,
            ),
            OpenApiParameter(
                name='user_subscription_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description='Filter by user subscription ID',
                required=False,
            ),
        ],
        responses={200: PaymentTransactionSerializer(many=True)},
        tags=['Payments'],
    )
    def list(self, request):
        """
        List user's payment transactions.

        GET /api/v1/subscriptions/payments/?status=success&user_subscription_id=xxx

        Filters:
        - status: Transaction status
        - user_subscription_id: Filter by subscription
        """
        queryset = self.get_queryset()

        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        user_subscription_id = request.query_params.get('user_subscription_id')
        if user_subscription_id:
            queryset = queryset.filter(user_subscription_id=user_subscription_id)

        # Order by most recent
        queryset = queryset.order_by('-created_at')

        # Paginate
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = PaymentTransactionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = PaymentTransactionSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Get Payment Transaction Details",
        description="Get detailed information about a specific payment transaction including all Hubtel callback data.",
        responses={
            200: PaymentTransactionSerializer,
            404: OpenApiTypes.OBJECT,
        },
        tags=['Payments'],
    )
    def retrieve(self, request, pk=None):
        """
        Get detailed information about a specific payment.

        GET /api/v1/subscriptions/payments/{id}/
        """
        try:
            transaction = self.get_queryset().get(pk=pk)
        except PaymentTransaction.DoesNotExist:
            return Response(
                {'error': 'Payment transaction not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = PaymentTransactionSerializer(transaction)
        return Response(serializer.data)

    @extend_schema(
        summary="Verify Payment with Hubtel API",
        description="Manually verify payment status by querying Hubtel's Status Check API. Requires Finance Admin or Super Admin role.",
        responses={
            200: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
            500: OpenApiTypes.OBJECT,
        },
        tags=['Payments', 'Admin'],
    )
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """
        Manually verify payment status with Hubtel API.
        Admin/Finance admin only.

        POST /api/v1/subscriptions/payments/{id}/verify/

        Queries Hubtel status API and updates local records.
        """
        # Check permissions
        if not (hasattr(request.user, 'is_finance_admin') and
                (request.user.is_finance_admin() or request.user.is_super_admin())):
            return Response(
                {'error': 'Permission denied. Finance admin access required.'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            transaction = PaymentTransaction.objects.get(pk=pk)
        except PaymentTransaction.DoesNotExist:
            return Response(
                {'error': 'Payment transaction not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            hubtel_service = HubtelPaymentService()
            transaction = hubtel_service.check_payment_status(transaction)

            serializer = PaymentTransactionSerializer(transaction)
            return Response({
                'message': 'Payment status verified with Hubtel',
                'transaction': serializer.data
            })

        except Exception as e:
            logger.error(f"Payment verification error: {e}", exc_info=True)
            return Response(
                {'error': f'Failed to verify payment: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @property
    def paginator(self):
        """
        The paginator instance associated with the view, or `None`.
        """
        if not hasattr(self, '_paginator'):
            if self.pagination_class is None:
                self._paginator = None
            else:
                self._paginator = self.pagination_class()
        return self._paginator

    def paginate_queryset(self, queryset):
        """
        Return a single page of results, or `None` if pagination is disabled.
        """
        if self.paginator is None:
            return None
        return self.paginator.paginate_queryset(queryset, self.request, view=self)

    def get_paginated_response(self, data):
        """
        Return a paginated style `Response` object for the given output data.
        """
        assert self.paginator is not None
        return self.paginator.get_paginated_response(data)

    pagination_class = None  # Will use default from settings

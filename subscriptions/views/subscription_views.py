from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from subscriptions.models import Subscription, UserSubscription
from subscriptions.serializers import SubscriptionSerializer, UserSubscriptionPaymentInfoSerializer

@extend_schema(tags=['Subscriptions'])
class SubscriptionViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriptionSerializer
    parser_classes = [JSONParser]
    permission_classes = [IsAuthenticated,]
    queryset = Subscription.objects.all()

    @extend_schema(
        summary="Get My Subscriptions",
        description="List all subscriptions assigned to the current user with payment information including status, amounts, and payment history.",
        parameters=[
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by payment status: fully_paid, partially_paid, overdue, not_paid, refunded',
                required=False,
            ),
        ],
        responses={200: UserSubscriptionPaymentInfoSerializer(many=True)},
    )
    @action(detail=False, methods=['get'], url_path='my-subscriptions')
    def my_subscriptions(self, request):
        """
        Get current user's assigned subscriptions with payment info.

        GET /api/v1/subscriptions/my-subscriptions/?status=not_paid

        Returns list of subscriptions assigned to the user with:
        - Subscription details (name, amount, dates)
        - Payment status and progress
        - Outstanding amount
        - user_subscription_id (needed for payment initiation)
        - Payment history
        """
        queryset = UserSubscription.objects.filter(
            user=request.user
        ).select_related('user', 'subscription').prefetch_related('payment_transactions')

        # Filter by status if provided
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Order by creation date (most recent first)
        queryset = queryset.order_by('-created_at')

        serializer = UserSubscriptionPaymentInfoSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Get Subscription Assignees",
        description="List all users assigned to a specific subscription with their payment information. Admin/Executive access required.",
        parameters=[
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by payment status: fully_paid, partially_paid, overdue, not_paid, refunded',
                required=False,
            ),
        ],
        responses={
            200: UserSubscriptionPaymentInfoSerializer(many=True),
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
    @action(detail=True, methods=['get'])
    def assignees(self, request, pk=None):
        """
        Get all users assigned to a subscription (Admin only).

        GET /api/v1/subscriptions/{id}/assignees/?status=not_paid

        Returns list of all assignees with payment info.
        Requires executive/admin role.
        """
        # Check if user is executive
        if not (hasattr(request.user, 'is_executive') and request.user.is_executive()):
            return Response(
                {'error': 'Permission denied. Executive access required.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get subscription
        try:
            subscription = Subscription.objects.get(pk=pk, organization=request.user.organization)
        except Subscription.DoesNotExist:
            return Response(
                {'error': 'Subscription not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get all user subscriptions for this subscription
        queryset = UserSubscription.objects.filter(
            subscription=subscription
        ).select_related('user', 'subscription').prefetch_related('payment_transactions')

        # Filter by status if provided
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Order by user name
        queryset = queryset.order_by('user__first_name', 'user__last_name')

        serializer = UserSubscriptionPaymentInfoSerializer(queryset, many=True)
        return Response(serializer.data)

from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from communication.serializers.sms_serializers import (
    SingleSMSRequestSerializer,
    SingleSMSResponseSerializer,
    BatchSMSRequestSerializer,
    BatchSMSResponseSerializer,
    SMSErrorResponseSerializer
)
from communication.services.sms_service import SMSService


@extend_schema(tags=['SMS'])
class SMSViewSet(viewsets.ViewSet):
    """
    ViewSet for SMS operations.
    Provides endpoints for sending single and batch SMS messages via Hubtel API.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Send Single SMS",
        description="Send an SMS message to a single recipient.",
        request=SingleSMSRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=SingleSMSResponseSerializer,
                description="SMS sent successfully"
            ),
            400: OpenApiResponse(
                response=SMSErrorResponseSerializer,
                description="Invalid request data"
            ),
            500: OpenApiResponse(
                response=SMSErrorResponseSerializer,
                description="SMS sending failed"
            ),
        }
    )
    @action(detail=False, methods=['post'], url_path='send-single')
    def send_single(self, request):
        """Send SMS to a single recipient."""
        serializer = SingleSMSRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid request data', 'detail': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        phone_number = serializer.validated_data['to']
        content = serializer.validated_data['content']
        
        result = SMSService.send_single_sms(phone_number, content)
        
        if result.success:
            response_data = {
                'rate': result.rate,
                'messageId': result.message_id,
                'status': result.status,
                'networkId': result.network_id,
                'clientReference': result.client_reference,
                'statusDescription': result.status_description
            }
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            return Response(
                {'error': 'Failed to send SMS', 'detail': result.error},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Send Batch SMS",
        description="Send an SMS message to multiple recipients in a single request.",
        request=BatchSMSRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=BatchSMSResponseSerializer,
                description="Batch SMS sent successfully"
            ),
            400: OpenApiResponse(
                response=SMSErrorResponseSerializer,
                description="Invalid request data"
            ),
            500: OpenApiResponse(
                response=SMSErrorResponseSerializer,
                description="Batch SMS sending failed"
            ),
        }
    )
    @action(detail=False, methods=['post'], url_path='send-batch')
    def send_batch(self, request):
        """Send SMS to multiple recipients."""
        serializer = BatchSMSRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid request data', 'detail': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        recipients = serializer.validated_data['recipients']
        content = serializer.validated_data['content']
        
        result = SMSService.send_batch_sms(recipients, content)
        
        if result.success:
            response_data = {
                'batchId': result.batch_id,
                'status': result.status,
                'data': [
                    {
                        'recipient': item.recipient,
                        'content': item.content,
                        'messageId': item.message_id
                    }
                    for item in (result.data or [])
                ]
            }
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            return Response(
                {'error': 'Failed to send batch SMS', 'detail': result.error},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

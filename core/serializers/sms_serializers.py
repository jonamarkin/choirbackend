from rest_framework import serializers


class SingleSMSRequestSerializer(serializers.Serializer):
    """Request serializer for sending single SMS."""
    to = serializers.CharField(
        max_length=20, 
        help_text="Recipient phone number (e.g., 233209335976)"
    )
    content = serializers.CharField(
        max_length=1600, 
        help_text="SMS message content"
    )


class SingleSMSResponseSerializer(serializers.Serializer):
    """Response serializer for single SMS send result."""
    rate = serializers.FloatField(allow_null=True)
    messageId = serializers.CharField(allow_null=True)
    status = serializers.IntegerField()
    networkId = serializers.CharField(allow_null=True)
    clientReference = serializers.CharField(allow_null=True)
    statusDescription = serializers.CharField()


class BatchSMSRequestSerializer(serializers.Serializer):
    """Request serializer for sending batch SMS."""
    recipients = serializers.ListField(
        child=serializers.CharField(max_length=20),
        min_length=1,
        max_length=1000,
        help_text="List of recipient phone numbers"
    )
    content = serializers.CharField(
        max_length=1600, 
        help_text="SMS message content to send to all recipients"
    )


class BatchRecipientResponseSerializer(serializers.Serializer):
    """Response serializer for a single recipient in batch result."""
    recipient = serializers.CharField()
    content = serializers.CharField()
    messageId = serializers.CharField()


class BatchSMSResponseSerializer(serializers.Serializer):
    """Response serializer for batch SMS send result."""
    batchId = serializers.CharField()
    status = serializers.IntegerField()
    data = BatchRecipientResponseSerializer(many=True)


class SMSErrorResponseSerializer(serializers.Serializer):
    """Error response serializer for SMS operations."""
    error = serializers.CharField()
    detail = serializers.CharField(required=False)

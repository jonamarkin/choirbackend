import requests
from django.conf import settings
from typing import Optional
from dataclasses import dataclass


@dataclass
class SingleSMSResponse:
    """Response structure for single SMS send."""
    success: bool
    rate: Optional[float] = None
    message_id: Optional[str] = None
    status: Optional[int] = None
    network_id: Optional[str] = None
    client_reference: Optional[str] = None
    status_description: Optional[str] = None
    error: Optional[str] = None


@dataclass
class BatchRecipientResult:
    """Result for a single recipient in batch SMS."""
    recipient: str
    content: str
    message_id: str


@dataclass
class BatchSMSResponse:
    """Response structure for batch SMS send."""
    success: bool
    batch_id: Optional[str] = None
    status: Optional[int] = None
    data: Optional[list] = None
    error: Optional[str] = None


class SMSService:
    @staticmethod
    def send_sms(phone_number: str, message: str) -> bool:
        """
        Send SMS via Hubtel API (legacy method for backward compatibility).
        """
        result = SMSService.send_single_sms(phone_number, message)
        return result.success

    @staticmethod
    def send_single_sms(phone_number: str, message: str) -> SingleSMSResponse:
        """
        Send SMS to a single recipient via Hubtel API.
        Returns structured response with full details.
        """
        config = settings.HUBTEL_CONFIG
        base_url = config.get('SMS_BASE_URL', 'https://sms.hubtel.com')
        url = f"{base_url}{config.get('SMS_SINGLE_PATH', '/v1/messages/send')}"
        
        # Hubtel API params
        params = {
            'clientid': config.get('SMS_CLIENT_ID'),
            'clientsecret': config.get('SMS_CLIENT_SECRET'),
            'from': config.get('SMS_SENDER_ID'),
            'to': phone_number,
            'content': message
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return SingleSMSResponse(
                success=True,
                rate=data.get('rate'),
                message_id=data.get('messageId'),
                status=data.get('status'),
                network_id=data.get('networkId'),
                client_reference=data.get('clientReference'),
                status_description=data.get('statusDescription')
            )
            
        except requests.RequestException as e:
            error_message = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_message = error_data.get('message', str(e))
                except (ValueError, KeyError):
                    error_message = e.response.text or str(e)
            
            print(f"Failed to send SMS: {error_message}")
            return SingleSMSResponse(
                success=False,
                error=error_message
            )

    @staticmethod
    def send_batch_sms(recipients: list, message: str, sender_id: str = None) -> BatchSMSResponse:
        """
        Send SMS to multiple recipients via Hubtel Batch API.
        
        Args:
            recipients: List of phone numbers
            message: SMS content to send
            sender_id: Optional custom sender ID (uses default from config if not provided)
        
        Returns:
            BatchSMSResponse with batch details
        """
        config = settings.HUBTEL_CONFIG
        base_url = config.get('SMS_BASE_URL', 'https://sms.hubtel.com')
        url = f"{base_url}{config.get('SMS_BATCH_PATH', '/v1/messages/batch/simple/send')}"
        
        # Build request payload
        payload = {
            'From': sender_id or config.get('SMS_SENDER_ID'),
            'Recipients': recipients,
            'Content': message
        }
        
        # Basic auth with client credentials
        auth = (config.get('SMS_CLIENT_ID'), config.get('SMS_CLIENT_SECRET'))
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(url, json=payload, auth=auth, headers=headers, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            
            # Parse recipient results
            recipient_results = []
            for item in data.get('data', []):
                recipient_results.append(BatchRecipientResult(
                    recipient=item.get('recipient'),
                    content=item.get('content'),
                    message_id=item.get('messageId')
                ))
            
            return BatchSMSResponse(
                success=True,
                batch_id=data.get('batchId'),
                status=data.get('status'),
                data=recipient_results
            )
            
        except requests.RequestException as e:
            error_message = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_message = error_data.get('message', str(e))
                except (ValueError, KeyError):
                    error_message = e.response.text or str(e)
            
            print(f"Failed to send batch SMS: {error_message}")
            return BatchSMSResponse(
                success=False,
                error=error_message
            )

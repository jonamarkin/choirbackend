import requests
from django.conf import settings

class SMSService:
    @staticmethod
    def send_sms(phone_number, message):
        """
        Send SMS via Hubtel API.
        """
        config = settings.HUBTEL_CONFIG
        url = config.get('SMS_API_URL', 'https://sms.hubtel.com/v1/messages/send')
        
        # Hubtel API params
        params = {
            'clientid': config.get('SMS_CLIENT_ID'),
            'clientsecret': config.get('SMS_CLIENT_SECRET'),
            'from': config.get('SMS_SENDER_ID'),
            'to': phone_number,
            'content': message
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            # Check for API specific error codes if needed, but 200 usually means accepted
            return True
            
        except requests.RequestException as e:
            print(f"Failed to send SMS: {e}")
            if hasattr(e, 'response') and e.response:
                 print(f"Response: {e.response.text}")
            return False

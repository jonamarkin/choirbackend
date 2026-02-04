import random
import string
from django.utils import timezone
from datetime import timedelta
from authentication.models import OTP
from core.services.email_service import EmailService
from communication.services.sms_service import SMSService

class OTPService:
    @staticmethod
    def generate_otp(target, purpose, user=None, channel='email'):
        """
        Generate a new OTP for the given target.
        Expires in 10 minutes.
        """
        # Generate 6-digit code
        code = ''.join(random.choices(string.digits, k=6))
        
        expires_at = timezone.now() + timedelta(minutes=10)
        
        # Invalidate previous unused OTPs for this target/purpose
        OTP.objects.filter(
            target=target,
            purpose=purpose,
            is_used=False
        ).update(is_used=True)
        
        otp = OTP.objects.create(
            user=user,
            target=target,
            code=code,
            purpose=purpose,
            expires_at=expires_at
        )
        
        # Send via Channel
        if channel == 'email' or channel == 'both':
            if '@' in target: # Simple check to avoid sending email to phone number
                 EmailService.send_otp_email(target, code, purpose)
            
        if channel == 'sms' or channel == 'both':
             # If target is phone number or we have user's phone
             phone = target
             if user and user.phone_number and '@' in target:
                 phone = user.phone_number
                 
             if phone and not '@' in phone: # explicit phone check
                 message = f"Your {purpose.replace('_', ' ')} code is: {code}. Expires in 10 mins."
                 SMSService.send_sms(phone, message)
             
        return otp

    @staticmethod
    def verify_otp(target, code, purpose):
        """
        Verify an OTP. Returns the OTP object if valid, None otherwise.
        """
        try:
            otp = OTP.objects.filter(
                target=target,
                purpose=purpose,
                code=code,
                is_used=False
            ).latest('created_at')
            
            if otp.is_valid():
                otp.is_used = True
                otp.save()
                return otp
            return None
            
        except OTP.DoesNotExist:
            return None

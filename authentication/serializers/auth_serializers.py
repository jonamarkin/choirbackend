from rest_framework import serializers
from authentication.models import OTP
from authentication.services import OTPService
from django.contrib.auth import get_user_model

User = get_user_model()

class VerifyEmailSerializer(serializers.Serializer):
    """
    Serializer for verifying email via OTP logic.
    """
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, min_length=6, max_length=6)
    
    def validate(self, attrs):
        email = attrs.get('email')
        code = attrs.get('otp')
        
        # Verify OTP
        otp_instance = OTPService.verify_otp(target=email, code=code, purpose='activation')
        
        if not otp_instance:
             raise serializers.ValidationError({"otp": "Invalid or expired OTP."})
             
        # Attach user to validated data for view
        try:
            user = User.objects.get(email=email)
            attrs['user'] = user
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "User with this email does not exist."})
            
        return attrs


class ResendOTPSerializer(serializers.Serializer):
    """
    Serializer for resending OTP.
    """
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email does not exist.")
        return value


class RequestPasswordResetSerializer(serializers.Serializer):
    """
    Serializer to request a password reset OTP.
    """
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email does not exist.")
        return value


class PasswordResetVerifySerializer(serializers.Serializer):
    """
    Serializer to verify OTP and set new password.
    """
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, min_length=6, max_length=6)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password_confirm": "Passwords do not match."})
            
        email = attrs.get('email')
        otp = attrs.get('otp')
        
        # Verify OTP
        otp_instance = OTPService.verify_otp(target=email, code=otp, purpose='password_reset')
        
        if not otp_instance:
             raise serializers.ValidationError({"otp": "Invalid or expired OTP."})
             
        # Attach user
        try:
            user = User.objects.get(email=email)
            attrs['user'] = user
        except User.DoesNotExist:
             raise serializers.ValidationError({"email": "User error."})
             
        return attrs

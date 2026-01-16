from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from django.http import JsonResponse
from rest_framework import status

class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Overrides the default account adapter to prevent redirects in API context.
    """
    def respond_user_inactive(self, request, user):
        """
        Return JSON response when user is inactive instead of redirecting.
        """
        from authentication.serializers import UserSerializer
        
        user_data = UserSerializer(user).data
        
        raise ImmediateHttpResponse(
            JsonResponse(
                {
                    'detail': 'Account created successfully. Your account is currently inactive pending admin approval.',
                    'code': 'account_inactive',
                    'user': user_data
                },
                status=status.HTTP_200_OK
            )
        )

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Overrides the default adapter to prevent redirects in API context.
    """

    def is_open_for_signup(self, request, sociallogin):
        return True

    def pre_social_login(self, request, sociallogin):
        """
        Debug/Force auto-connect logic.
        """
        import sys
        print(f"DEBUG: pre_social_login checked for {sociallogin.user.email}", file=sys.stderr)
        
        # Default logic should handle auto-connect if configured
        super().pre_social_login(request, sociallogin)
        
        # If we are here, it means auto-connect didn't happen (or simply finished pre-checks).
        # Check if user exists but isn't connected.
        if not sociallogin.is_existing:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            email = sociallogin.user.email
            print(f"DEBUG: Social user not existing. Checking for local user with email: {email}", file=sys.stderr)
            
            if email:
                try:
                    user = User.objects.get(email=email)
                    print(f"DEBUG: Found existing user: {user}. Connecting...", file=sys.stderr)
                    sociallogin.connect(request, user)
                    print(f"DEBUG: Connected successfully.", file=sys.stderr)
                except User.DoesNotExist:
                    print(f"DEBUG: No local user found with that email.", file=sys.stderr)

    def save_user(self, request, sociallogin, form=None):
        """
        Ensure user is saved even if form validation fails due to missing optional fields.
        Also mark as inactive pending approval.
        """
        user = super().save_user(request, sociallogin, form)
        user.is_active = False
        user.save()
        return user

    def on_authentication_error(self, request, provider_id, error=None, exception=None, extra_context=None):
        """
        Return JSON response instead of redirecting or rendering HTML.
        """
        raise ImmediateHttpResponse(
            JsonResponse(
                {'error': 'Social authentication failed', 'detail': str(error or exception)},
                status=status.HTTP_400_BAD_REQUEST
            )
        )

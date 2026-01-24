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
        from authentication.serializers.user_serializers import UserSerializer
        
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
        Invoked just before login.
        We override this to ensure that if a user with the same email exists,
        we automatically connect this social account to that user.
        """
        # Default logic
        super().pre_social_login(request, sociallogin)
        
        # If the user is not yet existing (not linked), check if we have a local user with this email
        if not sociallogin.is_existing:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            email = sociallogin.user.email
            
            if email:
                try:
                    user = User.objects.get(email=email)
                    # Use 'connect' to link this social account to the existing user
                    sociallogin.connect(request, user)
                except User.DoesNotExist:
                    pass

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

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from rest_framework.response import Response
from rest_framework import status

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Overrides the default adapter to prevent redirects in API context.
    """

    def is_open_for_signup(self, request, sociallogin):
        return True

    def save_user(self, request, sociallogin, form=None):
        """
        Ensure user is saved even if form validation fails due to missing optional fields.
        """
        user = super().save_user(request, sociallogin, form)
        return user

    def on_authentication_error(self, request, provider_id, error=None, exception=None, extra_context=None):
        """
        Return JSON response instead of redirecting or rendering HTML.
        """
        raise ImmediateHttpResponse(
            Response(
                {'error': 'Social authentication failed', 'detail': str(error or exception)},
                status=status.HTTP_400_BAD_REQUEST
            )
        )

"""
Custom middleware for API CSRF exemption
"""
from django.utils.deprecation import MiddlewareMixin


class DisableCSRFForAPIMiddleware(MiddlewareMixin):
    """
    Disable CSRF for API endpoints that use JWT authentication.
    """
    def process_request(self, request):
        # Exempt all /api/ endpoints from CSRF checks
        if request.path.startswith('/api/'):
            setattr(request, '_dont_enforce_csrf_checks', True)
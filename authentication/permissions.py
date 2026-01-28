from rest_framework import permissions

class IsApproved(permissions.BasePermission):
    """
    Custom permission to only allow approved users to access the view.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_active and request.user.is_approved

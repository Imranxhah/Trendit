from rest_framework import permissions

class IsProfileComplete(permissions.BasePermission):
    """
    Allows access only to authenticated users who have completed their profile.
    (First Name, Last Name, and Phone Number are provided)
    """
    message = "Your profile is incomplete. Please complete your profile to access this feature."

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.has_completed_profile
        )

class IsProfileCompleteOrReadOnly(permissions.BasePermission):
    """
    Allows read-only access to anyone, but write access requires a complete profile.
    """
    message = "Your profile is incomplete. Please complete your profile to perform this action."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.has_completed_profile
        )

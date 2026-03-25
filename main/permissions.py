from rest_framework.permissions import IsAuthenticated


class IsEmailVerified(IsAuthenticated):
    """
    Extends IsAuthenticated to also require email verification for examiners.
    Candidates and guests are exempt — they are always considered verified.
    """
    message = {"error": "email_not_verified", "message": "Please verify your email before continuing."}

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user = request.user
        if user.is_guest or user.role == user.Role.CANDIDATE:
            return True
        return user.is_verified

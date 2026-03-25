from django.urls import path

from .views import GuestJoinView, LoginView, LogoutView, MeView, RegisterView, ResendVerificationView, VerifyEmailView

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/verify-email/", VerifyEmailView.as_view(), name="auth-verify-email"),
    path("auth/resend-verification/", ResendVerificationView.as_view(), name="auth-resend-verification"),
    path("auth/guest-join/", GuestJoinView.as_view(), name="auth-guest-join"),
]

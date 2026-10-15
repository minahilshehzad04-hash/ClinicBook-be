from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    LoginView,
    LogoutView,
    MeView,
    PatientDashboardView,
    PatientRegisterView,
    ResendVerificationView,
    VerifyEmailView,
)

# Mounted at /api/v1/auth/
urlpatterns = [
    path("register/", PatientRegisterView.as_view(), name="patient-register"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify-email"),
    path("resend-verification/", ResendVerificationView.as_view(), name="resend-verification"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", MeView.as_view(), name="me"),
]

# Mounted at /api/v1/patients/
patient_urlpatterns = [
    path("dashboard/", PatientDashboardView.as_view(), name="patient-dashboard"),
]

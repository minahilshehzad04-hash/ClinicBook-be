
from django.urls import path

from .views import (
    PatientLoginView,
    PatientPortalView,
    PatientRegisterView,
)

urlpatterns = [
    path("register/", PatientRegisterView.as_view(), name="patient-register"),
    path("login/", PatientLoginView.as_view(), name="patient-login"),
    path("portal/", PatientPortalView.as_view(), name="patient-portal"),
]

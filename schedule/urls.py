from django.urls import path

from .views import (
    DoctorAppointmentRespondView,
    DoctorAppointmentsView,
    PatientAppointmentsView,
    ScheduleDetailView,
    ScheduleView,
)

urlpatterns = [
    # doctor schedule
    path("", ScheduleView.as_view(), name="doctor-schedule"),
    path("<int:pk>/", ScheduleDetailView.as_view(), name="doctor-schedule-detail"),

    # appointments
    path("appointments/", PatientAppointmentsView.as_view(), name="patient-appointments"),
    path("doctor/appointments/", DoctorAppointmentsView.as_view(), name="doctor-appointments"),
    path("doctor/appointments/<int:pk>/respond/", DoctorAppointmentRespondView.as_view(),
         name="doctor-appointment-respond"),
]
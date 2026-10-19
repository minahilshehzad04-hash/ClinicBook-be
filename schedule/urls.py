from django.urls import path

from .views import ScheduleDetailView, ScheduleView

urlpatterns = [
    path("", ScheduleView.as_view(), name="doctor-schedule"),
    path("<int:pk>/", ScheduleDetailView.as_view(), name="doctor-schedule-detail"),
]
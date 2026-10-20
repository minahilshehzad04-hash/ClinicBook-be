from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsDoctor

from .models import Appointment, Weekday, WeeklyAvailability
from .serializers import (
    AppointmentSerializer,
    DoctorListSerializer,
    SlotQuerySerializer,
    WeeklyAvailabilitySerializer,
)
from .services import generate_slots


def doctors_queryset():
    # Doctors = users who have at least one availability window.
    return get_user_model().objects.filter(availability__isnull=False).distinct()


class ScheduleView(APIView):
    """GET the doctor's week grouped by day, POST a new window. Doctors only."""

    permission_classes = [IsDoctor]

    def get(self, request):
        days = [{"weekday": v, "name": label, "slots": []} for v, label in Weekday.choices]
        windows = WeeklyAvailability.objects.filter(doctor=request.user)
        for w in windows:
            days[w.weekday]["slots"].append(
                WeeklyAvailabilitySerializer(w, context={"request": request}).data
            )
        return Response({"days": days})

    def post(self, request):
        s = WeeklyAvailabilitySerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        s.save(doctor=request.user)
        return Response(s.data, status=status.HTTP_201_CREATED)


class ScheduleDetailView(APIView):
    """PATCH or DELETE one of the signed-in doctor's own windows."""

    permission_classes = [IsDoctor]

    def _get(self, request, pk):
        return get_object_or_404(WeeklyAvailability, pk=pk, doctor=request.user)

    def patch(self, request, pk):
        s = WeeklyAvailabilitySerializer(
            self._get(request, pk), data=request.data, partial=True,
            context={"request": request},
        )
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)

    def delete(self, request, pk):
        self._get(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DoctorListView(APIView):
    """Patient-facing: doctors who have published availability."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(DoctorListSerializer(doctors_queryset(), many=True).data)


class DoctorSlotsView(APIView):
    """Patient-facing: available slots for one doctor."""

    permission_classes = [IsAuthenticated]

    def get(self, request, doctor_id):
        doctor = get_object_or_404(doctors_queryset(), pk=doctor_id)

        q = SlotQuerySerializer(data=request.query_params)
        q.is_valid(raise_exception=True)

        today = timezone.localdate()
        start = max(q.validated_data.get("start") or today, today)

        days = generate_slots(
            doctor,
            start_date=start,
            days=q.validated_data["days"],
            duration=q.validated_data["duration"],
        )
        return Response({"doctor_id": doctor.pk, "days": days})


class PatientAppointmentsView(APIView):
    """GET my appointments, POST a new request (status=pending)."""

    permission_classes = [IsAuthenticated]  # or your IsPatient

    def get(self, request):
        qs = (
            Appointment.objects.filter(patient=request.user)
            .select_related("doctor", "patient")
            .order_by("-start")
        )
        return Response(AppointmentSerializer(qs, many=True).data)

    def post(self, request):
        s = AppointmentSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            s.save(patient=request.user)  # patient comes from the token
        except IntegrityError:  # two people hit the same slot at once
            return Response({"error": "Slot just got taken.", "code": "slot_taken"}, status=409)
        return Response(s.data, status=status.HTTP_201_CREATED)


class DoctorAppointmentsView(APIView):
    """Doctor's inbox. Optional ?status=pending"""

    permission_classes = [IsDoctor]

    def get(self, request):
        qs = (
            Appointment.objects.filter(doctor=request.user)
            .select_related("doctor", "patient")
            .order_by("start")
        )
        status_param = request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        return Response(AppointmentSerializer(qs, many=True).data)


class DoctorAppointmentRespondView(APIView):
    """PATCH {"action": "accept"} or {"action": "reject"}"""

    permission_classes = [IsDoctor]

    def patch(self, request, pk):
        appt = get_object_or_404(Appointment, pk=pk, doctor=request.user)
        if appt.status != Appointment.Status.PENDING:
            return Response({"error": "This request was already handled."}, status=400)

        action = request.data.get("action")
        if action == "accept":
            appt.status = Appointment.Status.CONFIRMED
        elif action == "reject":
            appt.status = Appointment.Status.REJECTED
        else:
            return Response({"error": "Use 'accept' or 'reject'."}, status=400)

        appt.save(update_fields=["status", "updated_at"])
        return Response(AppointmentSerializer(appt).data)
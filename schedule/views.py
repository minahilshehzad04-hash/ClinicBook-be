from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsDoctor

from .models import Weekday, WeeklyAvailability
from .serializers import WeeklyAvailabilitySerializer


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
        s.save(doctor=request.user)   # the doctor comes from the token, never the body
        return Response(s.data, status=status.HTTP_201_CREATED)


class ScheduleDetailView(APIView):
    """PATCH or DELETE one of the signed-in doctor's own windows."""

    permission_classes = [IsDoctor]

    def _get(self, request, pk):
        # Filtering by doctor means another doctor's window is simply a 404.
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
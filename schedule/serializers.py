from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import Appointment, WeeklyAvailability
from accounts.models import DoctorProfile


def display_name(user):
    return user.get_full_name() or str(user)


class WeeklyAvailabilitySerializer(serializers.ModelSerializer):
    weekday_name = serializers.CharField(source="get_weekday_display", read_only=True)

    class Meta:
        model = WeeklyAvailability
        fields = ["id", "weekday", "weekday_name", "start_time", "end_time"]

    def validate(self, attrs):
        inst = self.instance
        weekday = attrs.get("weekday", inst.weekday if inst else None)
        start = attrs.get("start_time", inst.start_time if inst else None)
        end = attrs.get("end_time", inst.end_time if inst else None)

        if end <= start:
            raise serializers.ValidationError({"end_time": "End time must be after start time."})

        doctor = self.context["request"].user
        overlapping = WeeklyAvailability.objects.filter(
            doctor=doctor, weekday=weekday, start_time__lt=end, end_time__gt=start
        )
        if inst:
            overlapping = overlapping.exclude(pk=inst.pk)
        if overlapping.exists():
            raise serializers.ValidationError(
                {"start_time": "This overlaps another window on the same day."}
            )
        return attrs


class SlotQuerySerializer(serializers.Serializer):
    start = serializers.DateField(required=False)
    days = serializers.IntegerField(required=False, min_value=1, max_value=31, default=7)
    duration = serializers.IntegerField(required=False, min_value=10, max_value=240, default=30)


class DoctorPublicProfileSerializer(serializers.ModelSerializer):
    """Only what patients may see. No license number."""

    class Meta:
        model = DoctorProfile
        fields = ["specialty", "qualification", "years_of_experience",
                  "consultation_fee", "bio"]


class DoctorListSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = ["id", "name", "profile"]

    def get_name(self, obj):
        return display_name(obj)

    def get_profile(self, obj):
        profile = DoctorProfile.objects.filter(user=obj).first()
        return DoctorPublicProfileSerializer(profile).data if profile else {}


class AppointmentSerializer(serializers.ModelSerializer):
    # Only users who published availability can be booked
    doctor = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.filter(availability__isnull=False).distinct()
    )
    duration = serializers.IntegerField(write_only=True, min_value=10, max_value=240, default=30)
    patient_name = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            "id", "doctor", "doctor_name", "patient_name",
            "start", "end", "duration", "reason", "status",
        ]
        read_only_fields = ["end", "status"]

    def get_patient_name(self, obj):
        return display_name(obj.patient)

    def get_doctor_name(self, obj):
        return display_name(obj.doctor)

    def validate(self, attrs):
        doctor, start = attrs["doctor"], attrs["start"]
        end = start + timedelta(minutes=attrs.pop("duration"))

        if start <= timezone.now():
            raise serializers.ValidationError({"start": "This time is in the past."})

        # Must sit inside one of the doctor's weekly windows (clinic local time)
        ls, le = timezone.localtime(start), timezone.localtime(end)
        inside = WeeklyAvailability.objects.filter(
            doctor=doctor,
            weekday=ls.weekday(),
            start_time__lte=ls.time(),
            end_time__gte=le.time(),
        ).exists()
        if not inside:
            raise serializers.ValidationError({"start": "Doctor is not available at this time."})

        # Must not clash with an active appointment
        taken = Appointment.objects.filter(
            doctor=doctor, status__in=["pending", "confirmed"],
            start__lt=end, end__gt=start,
        ).exists()
        if taken:
            raise serializers.ValidationError(
                {"start": "This slot is already requested or booked."}
            )

        attrs["end"] = end
        return attrs
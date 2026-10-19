from rest_framework import serializers

from .models import WeeklyAvailability


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
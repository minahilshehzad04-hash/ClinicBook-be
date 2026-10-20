from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Weekday(models.IntegerChoices):
    MONDAY = 0, "Monday"
    TUESDAY = 1, "Tuesday"
    WEDNESDAY = 2, "Wednesday"
    THURSDAY = 3, "Thursday"
    FRIDAY = 4, "Friday"
    SATURDAY = 5, "Saturday"
    SUNDAY = 6, "Sunday"


class WeeklyAvailability(models.Model):
    """One working window for a doctor on one weekday, e.g. Monday 09:00-13:00."""

    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="availability",
    )
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["weekday", "start_time"]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")),
                name="availability_end_after_start",
            ),
            models.UniqueConstraint(
                fields=["doctor", "weekday", "start_time", "end_time"],
                name="availability_no_exact_duplicate",
            ),
        ] 
        indexes = [models.Index(fields=["doctor", "weekday"])]

    def __str__(self):
        return f"{self.doctor} {self.get_weekday_display()} {self.start_time}-{self.end_time}"



class Appointment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        CONFIRMED = "confirmed"
        REJECTED = "rejected"
        CANCELLED = "cancelled"

    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                related_name="appointments_as_patient")
    doctor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                               related_name="appointments_as_doctor")
    start = models.DateTimeField()
    end = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start"]
        constraints = [
            # Same doctor + same start can't have two active requests
            models.UniqueConstraint(
                fields=["doctor", "start"],
                condition=Q(status__in=["pending", "confirmed"]),
                name="one_active_appointment_per_slot",
            ),
        ]


        
    
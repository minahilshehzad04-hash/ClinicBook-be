from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models import Q


class CustomUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        # `createsuperuser` should produce an ADMIN, not the default patient.
        extra_fields.setdefault("role", "admin")
        # Staff accounts don't go through the email-verification step.
        extra_fields.setdefault("is_email_verified", True)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        DOCTOR = "doctor", "Doctor"
        PATIENT = "patient", "Patient"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.PATIENT,
    )

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    # Patients must click the emailed link before they can log in.
    is_email_verified = models.BooleanField(default=False)


    class Meta:
        constraints = [
            # A phone number may only belong to one account (blank = not set).
            models.UniqueConstraint(
                fields=["phone"],
                condition=~Q(phone=""),
                name="unique_non_blank_phone",
            ),
        ]

    def __str__(self):
        return f"{self.username} ({self.role})"

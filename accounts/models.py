from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models import Q
from django.core.validators import MaxValueValidator, MinValueValidator


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
    # Patients and doctors must click the emailed link before they can log in.
    is_email_verified = models.BooleanField(default=False)

    # Use the manager above so `createsuperuser` makes a verified ADMIN.
    objects = CustomUserManager()

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

# doctor professional
class DoctorProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.PROTECT, related_name="doctor_profile"
    )
    specialty = models.CharField(max_length=100, blank=True)
    qualification = models.CharField(max_length=200, blank=True)
    years_of_experience = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(70)]
    )
    license_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    consultation_fee = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    bio = models.TextField(blank=True, max_length=1000)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Dr. {self.user.last_name} ({self.specialty or 'no specialty'})"
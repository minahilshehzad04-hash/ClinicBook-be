from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from datetime import date
from .models import User, DoctorProfile


class PatientRegistrationSerializer(serializers.ModelSerializer):
    """Public sign-up form for patients AND doctors."""

    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )

    # Public sign-up may only create patients or doctors. "admin" is rejected
    # (the admin account is seeded, never self-registered).
    role = serializers.ChoiceField(
        choices=[
            (User.Role.PATIENT, "Patient"),
            (User.Role.DOCTOR, "Doctor"),
        ],
        default=User.Role.PATIENT,
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "password",
            "role",
            "first_name",
            "last_name",
            "phone",
            "date_of_birth",
        ]

    def validate_username(self, value):
        value = value.strip()

        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                "This username is already taken."
            )

        return value

    def validate_email(self, value):
        value = value.strip().lower()

        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "This email is already registered."
            )

        return value

    def create(self, validated_data):
        password = validated_data.pop("password")

        # `role` is already limited to patient/doctor by the field above.
        user = User(**validated_data)
        user.set_password(password)
        user.save()

        return user


class UserSummarySerializer(serializers.ModelSerializer):
    """Safe, read-only view of a user (no password)."""

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "date_of_birth",
            "role",
        ]
        read_only_fields = fields


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Personal fields any user may edit on themselves. No role, username or email."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone", "date_of_birth"]

    def validate_phone(self, value):
        value = value.strip()
        if value and User.objects.filter(phone=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("This phone number is already in use.")
        return value

    def validate_date_of_birth(self, value):
        if value and value > date.today():
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        return value


class DoctorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorProfile
        fields = ["specialty", "qualification", "years_of_experience",
                  "license_number", "consultation_fee", "bio"]

    def validate_license_number(self, value):
        return (value or "").strip() or None
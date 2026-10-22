from django.db import transaction
from django.db.models import Q
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .emails import send_verification_email
from .models import User, DoctorProfile
from .permissions import IsDoctor, IsPatient, IsAdmin
from .serializers import (
    DoctorProfileSerializer, RegistrationSerializer,
    ProfileUpdateSerializer, UserSummarySerializer,
)
from rest_framework.exceptions import ValidationError
from .tokens import email_token_generator


def build_auth_response(user, message, http_status=status.HTTP_200_OK):
    refresh = RefreshToken.for_user(user)   # create signed refresh token
    return Response(
        {
            "message": message,
            "user": UserSummarySerializer(user).data,
            "access": str(refresh.access_token),     # make access token
            "refresh": str(refresh),
        },
        status=http_status,
    )


class RegisterView(generics.CreateAPIView):
    """"New user" form for patients and doctors. Creates the account
    (unverified) and emails a verification link. The user is NOT signed in:
    they must verify first, then log in."""

    serializer_class = RegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = serializer.save()

        # Sent after the user is saved. If SMTP fails the account still exists
        # and the user can use "Resend" on the frontend.
        email_sent = send_verification_email(user)
        return Response(
            {
                "message": "Account created. Please check your email to verify it.",
                "email": user.email,
                "email_sent": email_sent,
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(APIView):
    """Called by the frontend /verify-email page with the uid + token from the link."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        uid = request.data.get("uid", "")
        token = request.data.get("token", "")

        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and user.is_email_verified:
            # Link clicked twice: treat as success so the user just goes to login.
            return Response({"message": "Email already verified."})

        if user is None or not email_token_generator.check_token(user, token):
            return Response(
                {
                    "error": "This verification link is invalid or has expired.",
                    "code": "invalid_or_expired_link",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
        return Response({"message": "Email verified. You can now log in."})


class ResendVerificationView(APIView):
    """Always answers 200 so nobody can discover which emails are registered."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "resend_verification"  # 5/hour per IP, see settings

    def post(self, request):
        email = str(request.data.get("email", "")).strip()
        user = User.objects.filter(
            email__iexact=email,
            role__in=[User.Role.PATIENT, User.Role.DOCTOR],
            is_email_verified=False,
            is_active=True,
        ).first()
        if user:
            send_verification_email(user)
        return Response(
            {"message": "If that account needs verifying, a new email is on its way."}
        )


class LoginView(APIView):
    """Login page for every role. `identifier` is the email or phone number.
    The response includes `user.role`, which the frontend uses to redirect."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"  # 5/min per IP, see REST_FRAMEWORK in settings

    def post(self, request):
        identifier = str(request.data.get("identifier", "")).strip()
        password = request.data.get("password", "")

        if not identifier or not password:
            return Response(
                {
                    "error": "Email or phone and password are required.",
                    "code": "missing_credentials",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(
            Q(email__iexact=identifier) | Q(phone=identifier)
        ).first()

        if not user or not user.check_password(password):
            return Response(
                {"error": "Invalid email/phone or password.", "code": "invalid_credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"error": "This account is deactivated.", "code": "account_deactivated"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Patients and doctors sign up themselves, so both must verify their
        # email. (The seeded admin is created already verified.)
        # Checked after the password, so this never reveals who has an account.
        if (
            user.role in (User.Role.PATIENT, User.Role.DOCTOR)
            and not user.is_email_verified
        ):
            return Response(
                {
                    "error": "Please verify your email before logging in.",
                    "code": "email_not_verified",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return build_auth_response(user, "Login successful.")


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            RefreshToken(request.data.get("refresh", "")).blacklist()
        
        except TokenError:
            return Response(
                {"error": "Invalid or expired refresh token.", "code": "invalid_token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_205_RESET_CONTENT)
    

class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSummarySerializer(request.user).data)

    def patch(self, request):
        s = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(UserSummarySerializer(request.user).data)


class DoctorProfileView(APIView):
    """PATCH the signed-in doctor's personal + professional details. Doctors only."""

    permission_classes = [IsDoctor]

    def patch(self, request):
        profile, _ = DoctorProfile.objects.get_or_create(user=request.user)
        user_s = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        prof_s = DoctorProfileSerializer(profile, data=request.data, partial=True)

        user_ok, prof_ok = user_s.is_valid(), prof_s.is_valid()
        if not (user_ok and prof_ok):
            raise ValidationError({**user_s.errors, **prof_s.errors})

        with transaction.atomic():   # both saved, or neither
            user_s.save()
            prof_s.save()

        return Response({
            "doctor": UserSummarySerializer(request.user).data,
            "profile": DoctorProfileSerializer(profile).data,
        })

class PatientDashboardView(APIView):
    """Landing page after login. Patients only."""

    permission_classes = [IsPatient]

    def get(self, request):
        return Response(
            {
                "message": f"Welcome, {request.user.first_name}.",
                "patient": UserSummarySerializer(request.user).data,
            }
        )


class DoctorDashboardView(APIView):
    """Landing page after login. Doctors only."""

    permission_classes = [IsDoctor]

    def get(self, request):
        user = request.user
        name = user.last_name or user.first_name or user.username
        profile, _ = DoctorProfile.objects.get_or_create(user=user)
        return Response(
            {
                "message": f"Welcome, Dr. {name}.",
                "doctor": UserSummarySerializer(user).data,
                "profile": DoctorProfileSerializer(profile).data,
            }
        )


class AdminDashboardView(APIView):
    """Landing page after login. Admins only."""

    permission_classes = [IsAdmin]

    def get(self, request):
        name = request.user.first_name or request.user.username
        recent = User.objects.exclude(role=User.Role.ADMIN).order_by("-date_joined")[:5]
        return Response(
            {
                "message": f"Welcome, {name}.",
                "admin": UserSummarySerializer(request.user).data,
                "stats": {
                    "patients": User.objects.filter(role=User.Role.PATIENT).count(),
                    "doctors": User.objects.filter(role=User.Role.DOCTOR).count(),
                    "unverified_users": User.objects.filter(
                        role__in=[User.Role.PATIENT, User.Role.DOCTOR],
                        is_email_verified=False,
                    ).count(),
                    "inactive_users": User.objects.filter(is_active=False).count(),
                },
                "recent_users": UserSummarySerializer(recent, many=True).data,
            }
        )        
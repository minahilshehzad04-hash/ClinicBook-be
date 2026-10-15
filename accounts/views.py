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
from .models import User
from .permissions import IsPatient
from .serializers import PatientRegistrationSerializer, UserSummarySerializer
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


class PatientRegisterView(generics.CreateAPIView):
    """"New user" form. Creates a patient (unverified) and emails a
    verification link. The patient is NOT signed in: they must verify first,
    then log in."""

    serializer_class = PatientRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = serializer.save()

        # Sent after the user is saved. If SMTP fails the account still exists
        # and the patient can use "Resend" on the frontend.
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
            role=User.Role.PATIENT,
            is_email_verified=False,
            is_active=True,
        ).first()
        if user:
            send_verification_email(user)
        return Response(
            {"message": "If that account needs verifying, a new email is on its way."}
        )


class LoginView(APIView):
    """Login page. `identifier` is the email or phone number."""

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

        # Only patients self-register, so only they need to verify their email.
        # (Checked after the password, so this never reveals who has an account.)
        if user.role == User.Role.PATIENT and not user.is_email_verified:
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
    """Current user's profile, any role."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSummarySerializer(request.user).data)


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

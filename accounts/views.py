
from django.db import transaction
from django.db.models import Q
from rest_framework import generics, permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import PatientRegistrationSerializer


class PatientRegisterView(generics.CreateAPIView):
    serializer_class = PatientRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)

        return Response({
            "message": "Patient registered successfully.",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
            },
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }, status=status.HTTP_201_CREATED)


class PatientLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        identifier = request.data.get("username", "").strip()
        password = request.data.get("password", "")

        if not identifier or not password:
            raise serializers.ValidationError(
                {"error": "Username/email and password are required."}
            )

        user = User.objects.filter(
            Q(username__iexact=identifier)
            | Q(email__iexact=identifier)
        ).first()

        if not user or not user.check_password(password):
            return Response(
                {"error": "Invalid username/email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"error": "Account is deactivated."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if user.role != User.Role.PATIENT:
            return Response(
                {"error": "Patient login only."},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)

        return Response({
            "message": "Login successful.",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
            },
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })


class PatientPortalView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role != User.Role.PATIENT:
            return Response(
                {"error": "Patient access only."},
                status=status.HTTP_403_FORBIDDEN,
            )

        user = request.user

        return Response({
            "message": "Welcome to your patient portal.",
            "patient": {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "phone": user.phone,
                "date_of_birth": user.date_of_birth,
            },
        })

from rest_framework.permissions import BasePermission

from .models import User


class HasRole(BasePermission):
    """Base class: user must be authenticated and have one of `allowed_roles`."""

    allowed_roles: tuple = ()
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.role in self.allowed_roles
        )


class IsPatient(HasRole):
    allowed_roles = (User.Role.PATIENT,)
    message = "Patient access only."


class IsAdmin(HasRole):
    allowed_roles = (User.Role.ADMIN,)
    message = "Admin access only."


class IsDoctor(HasRole):
    allowed_roles = (User.Role.DOCTOR,)
    message = "Doctor access only."

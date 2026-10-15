from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Every API error becomes {"error": "...", "code": "..."}."""
    response = exception_handler(exc, context)
    if response is None:
        return None  # unhandled -> Django's 500 handling

    if isinstance(exc, exceptions.ValidationError):
        return Response(
            {
                "error": "Validation failed.",
                "code": "validation_error",
                "details": response.data,
            },
            status=response.status_code,
        )

    detail = getattr(exc, "detail", None)
    message = str(detail) if detail is not None else "Request failed."
    code = getattr(exc, "default_code", "error")
    if isinstance(exc, exceptions.Throttled):
        message = "Too many attempts. Please try again later."
    return Response({"error": message, "code": code}, status=response.status_code)
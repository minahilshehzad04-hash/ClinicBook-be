from django.db import connection
from django.http import JsonResponse


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok", "db": "up"})
    except Exception:
        return JsonResponse({"status": "error", "db": "down"}, status=503)
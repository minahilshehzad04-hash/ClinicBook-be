"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path

from accounts.urls import doctor_urlpatterns, patient_urlpatterns


def health(request):
    """GET /health -- works without auth, reports DB status."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok", "db": "up"})
    except Exception:
        return JsonResponse({"status": "error", "db": "down"}, status=503)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health", health, name="health"),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/patients/", include((patient_urlpatterns, "patients"))),
    path("api/v1/doctors/schedule/", include("schedule.urls")),
    path("api/v1/doctors/", include("schedule.patient_urls")),
    path("api/v1/doctors/", include((doctor_urlpatterns, "doctors"))),
]
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User

REGISTER_URL = "/api/v1/auth/register/"
LOGIN_URL = "/api/v1/auth/login/"
LOGOUT_URL = "/api/v1/auth/logout/"
REFRESH_URL = "/api/v1/auth/token/refresh/"
DASHBOARD_URL = "/api/v1/patients/dashboard/"

PATIENT = {
    "first_name": "Ayesha",
    "last_name": "Khan",
    "email": "Ayesha@Example.com",
    "phone": "03001234567",
    "date_of_birth": "1998-04-12",
    "password": "Str0ng-Pass-9876",
    "confirm_password": "Str0ng-Pass-9876",
}


class RegistrationTests(APITestCase):
    def test_register_creates_patient_and_returns_tokens(self):
        res = self.client.post(REGISTER_URL, PATIENT, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)
        user = User.objects.get(email="ayesha@example.com")
        self.assertEqual(user.role, User.Role.PATIENT)
        self.assertNotEqual(user.password, PATIENT["password"])
        self.assertTrue(user.password.startswith("bcrypt_sha256$"))

    def test_role_in_request_is_ignored(self):
        res = self.client.post(REGISTER_URL, {**PATIENT, "role": "admin"}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(User.objects.get().role, User.Role.PATIENT)

    def test_duplicate_email_rejected_case_insensitive(self):
        self.client.post(REGISTER_URL, PATIENT, format="json")
        res = self.client.post(
            REGISTER_URL, {**PATIENT, "email": "AYESHA@example.com", "phone": "03111111111"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["code"], "validation_error")
        self.assertIn("email", res.data["details"])

    def test_duplicate_phone_rejected(self):
        self.client.post(REGISTER_URL, PATIENT, format="json")
        res = self.client.post(
            REGISTER_URL, {**PATIENT, "email": "other@example.com"}, format="json"
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("phone", res.data["details"])

    def test_password_mismatch(self):
        res = self.client.post(
            REGISTER_URL, {**PATIENT, "confirm_password": "different"}, format="json"
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("confirm_password", res.data["details"])

    def test_weak_password_rejected(self):
        res = self.client.post(
            REGISTER_URL, {**PATIENT, "password": "12345678", "confirm_password": "12345678"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("password", res.data["details"])

    def test_password_similar_to_name_reports_on_password_field(self):
        res = self.client.post(
            REGISTER_URL,
            {**PATIENT, "password": "Ayesha123", "confirm_password": "Ayesha123"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("password", res.data["details"])
        self.assertNotIn("non_field_errors", res.data["details"])

    def test_future_date_of_birth_rejected(self):
        res = self.client.post(
            REGISTER_URL, {**PATIENT, "date_of_birth": "2999-01-01"}, format="json"
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("date_of_birth", res.data["details"])

    def test_missing_fields_rejected(self):
        res = self.client.post(REGISTER_URL, {"email": "a@b.com"}, format="json")
        self.assertEqual(res.status_code, 400)


class LoginTests(APITestCase):
    def setUp(self):
        cache.clear()  # reset throttle counters between tests
        self.client.post(REGISTER_URL, PATIENT, format="json")

    def test_login_with_email(self):
        res = self.client.post(
            LOGIN_URL,
            {"identifier": "ayesha@example.com", "password": PATIENT["password"]},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["user"]["role"], "patient")

    def test_login_with_phone(self):
        res = self.client.post(
            LOGIN_URL,
            {"identifier": PATIENT["phone"], "password": PATIENT["password"]},
            format="json",
        )
        self.assertEqual(res.status_code, 200)

    def test_wrong_password(self):
        res = self.client.post(
            LOGIN_URL, {"identifier": "ayesha@example.com", "password": "nope"}, format="json"
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.data["code"], "invalid_credentials")

    def test_unknown_user_gets_same_error_as_wrong_password(self):
        res = self.client.post(
            LOGIN_URL, {"identifier": "ghost@example.com", "password": "x"}, format="json"
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.data["code"], "invalid_credentials")

    def test_missing_fields(self):
        res = self.client.post(LOGIN_URL, {}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_deactivated_account_cannot_login(self):
        User.objects.update(is_active=False)
        res = self.client.post(
            LOGIN_URL,
            {"identifier": "ayesha@example.com", "password": PATIENT["password"]},
            format="json",
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["code"], "account_deactivated")

    def test_login_is_rate_limited_to_5_per_minute(self):
        payload = {"identifier": "ayesha@example.com", "password": "wrong"}
        for _ in range(5):
            self.assertEqual(self.client.post(LOGIN_URL, payload, format="json").status_code, 401)
        res = self.client.post(LOGIN_URL, payload, format="json")
        self.assertEqual(res.status_code, 429)
        self.assertEqual(res.data["code"], "throttled")


class DashboardAndLogoutTests(APITestCase):
    def setUp(self):
        cache.clear()
        res = self.client.post(REGISTER_URL, PATIENT, format="json")
        self.access = res.data["access"]
        self.refresh = res.data["refresh"]

    def auth(self, token=None):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token or self.access}")

    def test_dashboard_requires_authentication(self):
        res = self.client.get(DASHBOARD_URL)
        self.assertEqual(res.status_code, 401)

    def test_patient_can_open_dashboard(self):
        self.auth()
        res = self.client.get(DASHBOARD_URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["patient"]["email"], "ayesha@example.com")

    def test_non_patient_gets_403_not_404(self):
        doctor = User.objects.create_user(
            username="doc", email="doc@example.com", password="Str0ng-Pass-9876",
            role=User.Role.DOCTOR,
        )
        from rest_framework_simplejwt.tokens import RefreshToken
        self.auth(str(RefreshToken.for_user(doctor).access_token))
        res = self.client.get(DASHBOARD_URL)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["code"], "permission_denied")

    def test_receptionist_role_exists(self):
        self.assertIn("receptionist", User.Role.values)

    def test_logout_blacklists_refresh_token(self):
        self.auth()
        res = self.client.post(LOGOUT_URL, {"refresh": self.refresh}, format="json")
        self.assertEqual(res.status_code, 205)
        self.client.credentials()
        res = self.client.post(REFRESH_URL, {"refresh": self.refresh}, format="json")
        self.assertEqual(res.status_code, 401)

    def test_logout_with_bad_token(self):
        self.auth()
        res = self.client.post(LOGOUT_URL, {"refresh": "garbage"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_refresh_returns_new_access_token(self):
        res = self.client.post(REFRESH_URL, {"refresh": self.refresh}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)

    def test_health_endpoint_works_without_auth(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
import pytest
from rest_framework.test import APIClient

from accounts.models import User

URL = "/api/v1/doctors/schedule/"
MON = {"weekday": 0, "start_time": "09:00", "end_time": "13:00"}


def make_user(name, role):
    return User.objects.create_user(
        username=name, email=f"{name}@t.test", password="Str0ng#Pass99",
        role=role, is_email_verified=True,
    )


def client_for(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.mark.django_db
def test_doctor_adds_window():
    c = client_for(make_user("doc1", "doctor"))
    assert c.post(URL, MON, format="json").status_code == 201
    days = c.get(URL).data["days"]
    assert len(days) == 7 and len(days[0]["slots"]) == 1


@pytest.mark.django_db
def test_overlap_and_bad_range_rejected():
    c = client_for(make_user("doc1", "doctor"))
    c.post(URL, MON, format="json")
    assert c.post(URL, {**MON, "start_time": "12:00", "end_time": "15:00"}, format="json").status_code == 400
    assert c.post(URL, {**MON, "start_time": "15:00", "end_time": "14:00"}, format="json").status_code == 400


@pytest.mark.django_db
def test_patient_gets_403():
    c = client_for(make_user("pat1", "patient"))
    assert c.get(URL).status_code == 403


@pytest.mark.django_db
def test_doctor_cannot_touch_another_doctors_window():
    c1 = client_for(make_user("doc1", "doctor"))
    wid = c1.post(URL, MON, format="json").data["id"]
    c2 = client_for(make_user("doc2", "doctor"))
    assert c2.delete(f"{URL}{wid}/").status_code == 404
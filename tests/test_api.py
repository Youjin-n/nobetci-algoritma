"""
API Integration Tests

FastAPI endpoint testleri - yeni şema ile uyumlu.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Test client"""
    return TestClient(app)


def create_user_payload(user_id: str, name: str) -> dict:
    """Şema uyumlu user payload oluştur"""
    return {
        "id": user_id,
        "name": name,
        "email": f"{user_id}@test.com",
        "likesNight": False,
        "dislikesWeekend": False,
        "history": {
            "weekdayCount": 0,
            "weekendCount": 0,
            "expectedTotal": 0,
            "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}
        }
    }


def create_slot_payload(slot_id: str, slot_date: str, duty_type: str, day_type: str = "WEEKDAY", seat_count: int = 1) -> dict:
    """Şema uyumlu slot payload oluştur"""
    return {
        "id": slot_id,
        "date": slot_date,
        "dutyType": duty_type,
        "dayType": day_type,
        "seats": [{"id": f"{slot_id}_s{i}", "role": None} for i in range(seat_count)]
    }


class TestScheduleEndpoint:
    """POST /schedule/compute endpoint testleri"""

    def test_compute_schedule_basic(self, client: TestClient):
        """Basit bir request ile schedule hesaplama"""
        request_data = {
            "period": {
                "id": "period-1",
                "name": "Test Period",
                "startDate": "2025-12-01",
                "endDate": "2025-12-31",
            },
            "users": [
                create_user_payload("user-1", "User One"),
                create_user_payload("user-2", "User Two"),
            ],
            "slots": [
                create_slot_payload("slot-1", "2025-12-01", "A"),
                create_slot_payload("slot-2", "2025-12-02", "B"),
            ],
            "unavailability": [],
        }

        response = client.post("/schedule/compute", json=request_data)

        assert response.status_code == 200

        data = response.json()
        assert "assignments" in data
        assert "meta" in data
        assert len(data["assignments"]) == 2
        assert data["meta"]["base"] == 1

    def test_compute_schedule_with_unavailability(self, client: TestClient):
        """Unavailability ile schedule hesaplama"""
        request_data = {
            "period": {
                "id": "period-1",
                "name": "Test Period",
                "startDate": "2025-12-01",
                "endDate": "2025-12-31",
            },
            "users": [
                create_user_payload("user-1", "User One"),
                create_user_payload("user-2", "User Two"),
            ],
            "slots": [
                create_slot_payload("slot-1", "2025-12-01", "A"),
            ],
            "unavailability": [{"userId": "user-1", "slotId": "slot-1"}],
        }

        response = client.post("/schedule/compute", json=request_data)

        assert response.status_code == 200

        data = response.json()
        # user-1 kapalı, slot-1'e user-2 atanmalı
        assert len(data["assignments"]) == 1
        assert data["assignments"][0]["userId"] == "user-2"

    def test_compute_schedule_response_format(self, client: TestClient):
        """Response formatı kontrolü"""
        request_data = {
            "period": {
                "id": "period-1",
                "name": "Test Period",
                "startDate": "2025-12-01",
                "endDate": "2025-12-31",
            },
            "users": [create_user_payload("user-1", "User One")],
            "slots": [create_slot_payload("slot-1", "2025-12-01", "A")],
            "unavailability": [],
        }

        response = client.post("/schedule/compute", json=request_data)
        data = response.json()

        # Meta alanlarını kontrol et
        meta = data["meta"]
        assert "base" in meta
        assert "maxShifts" in meta
        assert "minShifts" in meta
        assert "totalSlots" in meta
        assert "solverStatus" in meta
        assert "solveTimeMs" in meta

        # Assignment alanlarını kontrol et
        if data["assignments"]:
            assignment = data["assignments"][0]
            assert "slotId" in assignment
            assert "userId" in assignment
            assert "seatId" in assignment

    def test_validation_error_empty_users(self, client: TestClient):
        """Users boş olunca 422 dönmeli"""
        request_data = {
            "period": {
                "id": "period-1",
                "name": "Test Period",
                "startDate": "2025-12-01",
                "endDate": "2025-12-31",
            },
            "users": [],  # Boş
            "slots": [create_slot_payload("slot-1", "2025-12-01", "A")],
            "unavailability": [],
        }

        response = client.post("/schedule/compute", json=request_data)
        assert response.status_code == 422

    def test_validation_error_empty_slots(self, client: TestClient):
        """Slots boş olunca 422 dönmeli"""
        request_data = {
            "period": {
                "id": "period-1",
                "name": "Test Period",
                "startDate": "2025-12-01",
                "endDate": "2025-12-31",
            },
            "users": [create_user_payload("user-1", "User One")],
            "slots": [],  # Boş
            "unavailability": [],
        }

        response = client.post("/schedule/compute", json=request_data)
        assert response.status_code == 422

    def test_validation_error_invalid_duty_type(self, client: TestClient):
        """Geçersiz dutyType 422 dönmeli"""
        request_data = {
            "period": {
                "id": "period-1",
                "name": "Test Period",
                "startDate": "2025-12-01",
                "endDate": "2025-12-31",
            },
            "users": [create_user_payload("user-1", "User One")],
            "slots": [
                {
                    "id": "slot-1",
                    "date": "2025-12-01",
                    "dutyType": "X",  # Geçersiz
                    "dayType": "WEEKDAY",
                    "seats": [{"id": "s1", "role": None}]
                }
            ],
            "unavailability": [],
        }

        response = client.post("/schedule/compute", json=request_data)
        assert response.status_code == 422


class TestScheduleSeniorEndpoint:
    """POST /schedule/compute-senior endpoint testleri"""

    def create_senior_user_payload(self, user_id: str, name: str) -> dict:
        return {
            "id": user_id,
            "name": name,
            "email": f"{user_id}@test.com",
            "likesMorning": False,
            "likesEvening": False,
            "history": {
                "totalAllTime": 0,
                "countAAllTime": 0,
                "countMorningAllTime": 0,
                "countEveningAllTime": 0,
            }
        }

    def create_senior_slot_payload(self, slot_id: str, slot_date: str, segment: str) -> dict:
        return {
            "id": slot_id,
            "date": slot_date,
            "dutyType": "A",
            "segment": segment,
            "seats": [{"id": f"{slot_id}_s0", "role": None}]
        }

    def test_compute_senior_schedule_basic(self, client: TestClient):
        """Senior basit request"""
        request_data = {
            "period": {
                "id": "period-1",
                "name": "Senior Test Period",
                "startDate": "2025-12-01",
                "endDate": "2025-12-31",
            },
            "users": [
                self.create_senior_user_payload("senior-1", "Senior One"),
                self.create_senior_user_payload("senior-2", "Senior Two"),
            ],
            "slots": [
                self.create_senior_slot_payload("slot-1", "2025-12-01", "MORNING"),
                self.create_senior_slot_payload("slot-2", "2025-12-01", "EVENING"),
            ],
            "unavailability": [],
        }

        response = client.post("/schedule/compute-senior", json=request_data)

        assert response.status_code == 200

        data = response.json()
        assert "assignments" in data
        assert "meta" in data
        assert len(data["assignments"]) == 2

    def test_senior_validation_error_empty_users(self, client: TestClient):
        """Senior users boş olunca 422"""
        request_data = {
            "period": {
                "id": "period-1",
                "name": "Senior Test Period",
                "startDate": "2025-12-01",
                "endDate": "2025-12-31",
            },
            "users": [],
            "slots": [self.create_senior_slot_payload("slot-1", "2025-12-01", "MORNING")],
            "unavailability": [],
        }

        response = client.post("/schedule/compute-senior", json=request_data)
        assert response.status_code == 422

    def test_senior_validation_error_invalid_segment(self, client: TestClient):
        """Geçersiz segment 422"""
        request_data = {
            "period": {
                "id": "period-1",
                "name": "Senior Test Period",
                "startDate": "2025-12-01",
                "endDate": "2025-12-31",
            },
            "users": [self.create_senior_user_payload("senior-1", "Senior One")],
            "slots": [
                {
                    "id": "slot-1",
                    "date": "2025-12-01",
                    "dutyType": "A",
                    "segment": "INVALID",  # Geçersiz
                    "seats": [{"id": "s1", "role": None}]
                }
            ],
            "unavailability": [],
        }

        response = client.post("/schedule/compute-senior", json=request_data)
        assert response.status_code == 422


class TestHealthEndpoint:
    """Health check endpoint testi"""

    def test_root_endpoint(self, client: TestClient):
        """Root endpoint çalışıyor mu"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data

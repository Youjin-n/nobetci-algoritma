"""
Senior Scheduler Tests

Nöbetçi Asistan scheduler için testler.
"""

from datetime import date, timedelta

import pytest

from app.schemas.schedule_senior import (
    Segment,
    SeniorScheduleRequest,
    SeniorSlot,
    SeniorUnavailability,
    SeniorUser,
    SeniorUserHistory,
    SeniorSeat,
)
from app.schemas.schedule import Period
from app.services.scheduler.senior_solver import SeniorSchedulerSolver


# --- Fixtures ---

@pytest.fixture
def solver():
    """Solver instance"""
    return SeniorSchedulerSolver()


@pytest.fixture
def base_period():
    """Test period"""
    return Period(
        id="test-period",
        name="Test Period",
        startDate=date(2025, 12, 1),
        endDate=date(2025, 12, 31),
    )


def create_senior_user(
    user_id: str,
    name: str,
    history_a: int = 0,
    likes_morning: bool = False,
    likes_evening: bool = False,
) -> SeniorUser:
    """Helper to create senior user"""
    return SeniorUser(
        id=user_id,
        name=name,
        email=f"{user_id}@example.com",
        role="SENIOR_ASSISTANT",
        history=SeniorUserHistory(
            totalAllTime=history_a,
            countAAllTime=history_a,
        ),
        likesMorning=likes_morning,
        likesEvening=likes_evening,
    )


def create_senior_slot(
    slot_id: str,
    slot_date: date,
    segment: Segment,
    required_count: int = 1,
) -> SeniorSlot:
    """Helper to create senior slot"""
    seats = [SeniorSeat(id=f"{slot_id}_s{i}", role=None) for i in range(required_count)]
    return SeniorSlot(
        id=slot_id,
        slot_date=slot_date,
        dutyType="A",
        segment=segment,
        seats=seats
    )


# --- Basic Distribution Tests ---

class TestSeniorBasicDistribution:
    """Temel dağıtım testleri"""

    def test_equal_distribution_2_users_4_slots(self, solver, base_period):
        """2 kullanıcı, 4 slot: eşit dağıtım"""
        users = [
            create_senior_user("senior-1", "Dr. Ahmet"),
            create_senior_user("senior-2", "Dr. Mehmet"),
        ]

        slots = [
            create_senior_slot("s1", date(2025, 12, 1), Segment.MORNING),
            create_senior_slot("s2", date(2025, 12, 1), Segment.EVENING),
            create_senior_slot("s3", date(2025, 12, 2), Segment.MORNING),
            create_senior_slot("s4", date(2025, 12, 2), Segment.EVENING),
        ]

        request = SeniorScheduleRequest(
            period=base_period,
            users=users,
            slots=slots,
            unavailability=[],
        )

        response = solver.solve(request)

        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE")
        assert len(response.assignments) == 4
        assert response.meta.base == 2  # 4 slots / 2 users

        # Her kullanıcı 2 nöbet almalı
        user_counts = {}
        for assignment in response.assignments:
            user_counts[assignment.userId] = user_counts.get(assignment.userId, 0) + 1

        assert user_counts.get("senior-1", 0) == 2
        assert user_counts.get("senior-2", 0) == 2

    def test_10_users_20_slots(self, solver, base_period):
        """10 kullanıcı, 20 slot: eşit dağıtım"""
        users = [create_senior_user(f"senior-{i}", f"Dr. User {i}") for i in range(1, 11)]

        slots = []
        for day in range(10):
            slot_date = date(2025, 12, 1) + timedelta(days=day)
            slots.append(create_senior_slot(f"m{day}", slot_date, Segment.MORNING))
            slots.append(create_senior_slot(f"e{day}", slot_date, Segment.EVENING))

        request = SeniorScheduleRequest(
            period=base_period,
            users=users,
            slots=slots,
            unavailability=[],
        )

        response = solver.solve(request)

        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE")
        assert len(response.assignments) == 20
        assert response.meta.base == 2  # 20 slots / 10 users

        # Dağıtım dengeli olmalı
        user_counts = {}
        for assignment in response.assignments:
            user_counts[assignment.userId] = user_counts.get(assignment.userId, 0) + 1

        counts = list(user_counts.values())
        assert max(counts) - min(counts) <= 1  # En fazla 1 fark


class TestSeniorUnavailability:
    """Unavailability testleri"""

    def test_unavailability_respected(self, solver, base_period):
        """Unavailability'e saygı duyulmalı"""
        users = [
            create_senior_user("senior-1", "Dr. Ahmet"),
            create_senior_user("senior-2", "Dr. Mehmet"),
        ]

        slots = [
            create_senior_slot("s1", date(2025, 12, 1), Segment.MORNING),
            create_senior_slot("s2", date(2025, 12, 1), Segment.EVENING),
        ]

        # senior-1, s1'e müsait değil
        unavailability = [SeniorUnavailability(userId="senior-1", slotId="s1")]

        request = SeniorScheduleRequest(
            period=base_period,
            users=users,
            slots=slots,
            unavailability=unavailability,
        )

        response = solver.solve(request)

        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE")

        # s1'e senior-2 atanmalı
        s1_assignments = [a for a in response.assignments if a.slotId == "s1"]
        assert len(s1_assignments) == 1
        assert s1_assignments[0].userId == "senior-2"

    def test_unavailability_violation_warning(self, solver, base_period):
        """Herkes kapalıysa uyarı verilmeli"""
        users = [
            create_senior_user("senior-1", "Dr. Ahmet"),
            create_senior_user("senior-2", "Dr. Mehmet"),
        ]

        slots = [
            create_senior_slot("s1", date(2025, 12, 1), Segment.MORNING),
        ]

        # Herkes kapalı
        unavailability = [
            SeniorUnavailability(userId="senior-1", slotId="s1"),
            SeniorUnavailability(userId="senior-2", slotId="s1"),
        ]

        request = SeniorScheduleRequest(
            period=base_period,
            users=users,
            slots=slots,
            unavailability=unavailability,
        )

        response = solver.solve(request)

        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE")
        assert response.meta.unavailabilityViolations >= 1
        assert any("unavailability" in w.lower() for w in response.meta.warnings)


class TestSeniorDayLimit:
    """Günde max 2 segment testi"""

    def test_same_day_both_segments_allowed(self, solver, base_period):
        """Aynı gün sabah+akşam alınabilir"""
        users = [
            create_senior_user("senior-1", "Dr. Ahmet"),
        ]

        slots = [
            create_senior_slot("s1", date(2025, 12, 1), Segment.MORNING),
            create_senior_slot("s2", date(2025, 12, 1), Segment.EVENING),
        ]

        request = SeniorScheduleRequest(
            period=base_period,
            users=users,
            slots=slots,
            unavailability=[],
        )

        response = solver.solve(request)

        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE")
        assert len(response.assignments) == 2

        # Tek kullanıcı her iki segmenti de almalı
        assert all(a.userId == "senior-1" for a in response.assignments)


class TestSeniorConsecutiveDays:
    """Ardışık gün testleri"""

    def test_avoid_3_consecutive_days(self, solver, base_period):
        """3 gün üst üste mümkünse kaçınılmalı"""
        users = [
            create_senior_user("senior-1", "Dr. Ahmet"),
            create_senior_user("senior-2", "Dr. Mehmet"),
        ]

        # 3 ardışık gün, her gün 1 slot
        slots = [
            create_senior_slot("s1", date(2025, 12, 1), Segment.MORNING),
            create_senior_slot("s2", date(2025, 12, 2), Segment.MORNING),
            create_senior_slot("s3", date(2025, 12, 3), Segment.MORNING),
            create_senior_slot("s4", date(2025, 12, 4), Segment.MORNING),
        ]

        request = SeniorScheduleRequest(
            period=base_period,
            users=users,
            slots=slots,
            unavailability=[],
        )

        response = solver.solve(request)

        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE")

        # Her kullanıcının aldığı günleri kontrol et
        user_dates = {}
        for assignment in response.assignments:
            slot = next(s for s in slots if s.id == assignment.slotId)
            if assignment.userId not in user_dates:
                user_dates[assignment.userId] = []
            user_dates[assignment.userId].append(slot.slot_date)

        # Hiçbir kullanıcı 3 ardışık gün almamalı (mümkünse)
        for user_id, dates in user_dates.items():
            sorted_dates = sorted(dates)
            has_3_consecutive = False
            for i in range(len(sorted_dates) - 2):
                d1, d2, d3 = sorted_dates[i], sorted_dates[i + 1], sorted_dates[i + 2]
                if (d2 - d1).days == 1 and (d3 - d2).days == 1:
                    has_3_consecutive = True
                    break
            # 4 slot, 2 kişi = kişi başı 2 slot, 3 ardışık gün olmamalı
            assert not has_3_consecutive, f"{user_id} has 3 consecutive days"


class TestSeniorPreferences:
    """Tercih testleri"""

    def test_morning_preference_respected(self, solver, base_period):
        """Sabah tercihi dikkate alınmalı"""
        users = [
            create_senior_user("senior-1", "Dr. Ahmet", likes_morning=True),
            create_senior_user("senior-2", "Dr. Mehmet", likes_evening=True),
        ]

        slots = [
            create_senior_slot("m1", date(2025, 12, 1), Segment.MORNING),
            create_senior_slot("e1", date(2025, 12, 1), Segment.EVENING),
        ]

        request = SeniorScheduleRequest(
            period=base_period,
            users=users,
            slots=slots,
            unavailability=[],
        )

        response = solver.solve(request)

        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE")

        # senior-1 sabahı, senior-2 akşamı almalı (tercihler nedeniyle)
        morning_assignment = next(a for a in response.assignments if a.slotId == "m1")
        evening_assignment = next(a for a in response.assignments if a.slotId == "e1")

        assert morning_assignment.userId == "senior-1"
        assert evening_assignment.userId == "senior-2"


class TestSeniorBasePlus2:
    """Base+2 limit testleri"""

    def test_base_plus_2_respected(self, solver, base_period):
        """Base+2 limiti aşılmamalı"""
        users = [
            create_senior_user("senior-1", "Dr. Ahmet"),
            create_senior_user("senior-2", "Dr. Mehmet"),
        ]

        # 6 slot, base=3, base+2=5
        slots = [
            create_senior_slot(f"s{i}", date(2025, 12, 1) + timedelta(days=i), Segment.MORNING)
            for i in range(6)
        ]

        request = SeniorScheduleRequest(
            period=base_period,
            users=users,
            slots=slots,
            unavailability=[],
        )

        response = solver.solve(request)

        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE")

        # Hiçbir kullanıcı base+2=5'i aşmamalı
        user_counts = {}
        for assignment in response.assignments:
            user_counts[assignment.userId] = user_counts.get(assignment.userId, 0) + 1

        for user_id, count in user_counts.items():
            assert count <= 5, f"{user_id} has {count} shifts, max allowed is 5"


class TestSeniorMeta:
    """Meta bilgi testleri"""

    def test_meta_contains_required_fields(self, solver, base_period):
        """Meta tüm gerekli alanları içermeli"""
        users = [create_senior_user("senior-1", "Dr. Ahmet")]
        slots = [create_senior_slot("s1", date(2025, 12, 1), Segment.MORNING)]

        request = SeniorScheduleRequest(
            period=base_period,
            users=users,
            slots=slots,
            unavailability=[],
        )

        response = solver.solve(request)

        assert response.meta.base >= 0
        assert response.meta.maxShifts >= 0
        assert response.meta.minShifts >= 0
        assert response.meta.totalSlots == 1
        assert response.meta.totalAssignments >= 0
        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE", "INFEASIBLE")
        assert response.meta.solveTimeMs >= 0
        assert isinstance(response.meta.warnings, list)


class TestSeniorSeatRole:
    """Seat role testleri"""

    def test_seat_role_for_senior_1_person(self, solver, base_period):
        """1 kişi: 0 DESK, 1 OPERATOR -> OPERATOR olmalı"""
        users = [create_senior_user("senior-1", "Dr. Ahmet")]
        slots = [create_senior_slot("s1", date(2025, 12, 1), Segment.MORNING)]

        request = SeniorScheduleRequest(
            period=base_period,
            users=users,
            slots=slots,
            unavailability=[],
        )

        response = solver.solve(request)

        assert len(response.assignments) == 1
        # 1 kişi = OPERATOR
        assert response.assignments[0].seatRole.value == "OPERATOR"

    def test_seat_role_for_senior_2_persons(self, solver, base_period):
        """2 kişi: 1 DESK, 1 OPERATOR"""
        users = [
            create_senior_user("senior-1", "Dr. Ahmet"),
            create_senior_user("senior-2", "Dr. Mehmet"),
        ]
        slots = [create_senior_slot("s1", date(2025, 12, 1), Segment.MORNING, required_count=2)]

        request = SeniorScheduleRequest(
            period=base_period,
            users=users,
            slots=slots,
            unavailability=[],
        )

        response = solver.solve(request)

        assert len(response.assignments) == 2
        roles = [a.seatRole.value for a in response.assignments]
        assert roles.count("DESK") == 1
        assert roles.count("OPERATOR") == 1

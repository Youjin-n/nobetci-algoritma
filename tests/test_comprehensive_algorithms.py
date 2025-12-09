"""
Comprehensive Algorithm Tests - AÖ ve NA

Çeşitli zorlu senaryolarla her iki algoritmayı test eder:
1. Normal dağılım
2. Çarşamba yığılması (herkes aynı günü kapatmış)
3. Gece nöbeti yığılması (herkesin gece kapalı)
4. Az kişi çok slot (uç durum)
5. Çok kişi az slot
"""

import pytest
from datetime import date, timedelta
from app.services.scheduler.solver import SchedulerSolver
from app.services.scheduler.senior_solver import SeniorSchedulerSolver
from app.schemas.schedule import (
    ScheduleRequest, User, Slot, Unavailability, Period, UserHistory, Seat, SlotTypeCounts
)
from app.schemas.schedule_senior import (
    SeniorScheduleRequest, SeniorUser, SeniorSlot, SeniorUserHistory, SeniorSeat, 
    SeniorUnavailability, Segment
)


# ============================================================================
# TEST HELPERS
# ============================================================================

def create_ao_user(user_id: str, name: str, likes_night: bool = False, dislikes_weekend: bool = False) -> User:
    """AÖ kullanıcısı oluştur (geçmiş yok)"""
    return User(
        id=user_id,
        name=name,
        likesNight=likes_night,
        dislikesWeekend=dislikes_weekend,
        history=UserHistory(
            weekdayCount=0,
            weekendCount=0,
            expectedTotal=0,
            slotTypeCounts=SlotTypeCounts(A=0, B=0, C=0, D=0, E=0, F=0)
        )
    )


def create_ao_slot(slot_id: str, slot_date: date, duty_type: str, seat_count: int = 2) -> Slot:
    """AÖ slotu oluştur"""
    from app.schemas.schedule import DayType
    day_type = DayType.WEEKEND if duty_type in ("D", "E", "F") else DayType.WEEKDAY
    seats = [Seat(id=f"{slot_id}_s{i}", role=None) for i in range(seat_count)]
    return Slot(id=slot_id, date=slot_date, dutyType=duty_type, dayType=day_type, seats=seats)


def create_na_user(user_id: str, name: str, likes_morning: bool = False, likes_evening: bool = False) -> SeniorUser:
    """NA kullanıcısı oluştur (geçmiş yok)"""
    return SeniorUser(
        id=user_id,
        name=name,
        role="SENIOR_ASSISTANT",
        likesMorning=likes_morning,
        likesEvening=likes_evening,
        history=SeniorUserHistory(
            totalAllTime=0,
            countAAllTime=0,
            countMorningAllTime=0,
            countEveningAllTime=0
        )
    )


def create_na_slot(slot_id: str, slot_date: date, segment: Segment, seat_count: int = 2) -> SeniorSlot:
    """NA slotu oluştur"""
    seats = [SeniorSeat(id=f"{slot_id}_s{i}", role=None) for i in range(seat_count)]
    return SeniorSlot(id=slot_id, date=slot_date, segment=segment, seats=seats)


def print_distribution(response, label: str):
    """Dağılımı yazdır"""
    user_counts = {}
    for a in response.assignments:
        user_counts[a.userId] = user_counts.get(a.userId, 0) + 1
    
    print(f"\n{'='*60}")
    print(f"{label}")
    print(f"{'='*60}")
    print(f"Status: {response.meta.solverStatus}")
    print(f"Base: {response.meta.base}, Min: {response.meta.minShifts}, Max: {response.meta.maxShifts}")
    print(f"Unavailability violations: {response.meta.unavailabilityViolations}")
    print(f"Solve time: {response.meta.solveTimeMs:.0f}ms")
    print(f"\nDağılım:")
    for uid, count in sorted(user_counts.items()):
        print(f"  {uid}: {count}")
    
    if response.meta.warnings:
        print(f"\nWarnings: {response.meta.warnings}")


# ============================================================================
# AÖ TESTS
# ============================================================================

class TestAOAlgorithm:
    """AÖ Algoritması Testleri"""
    
    @pytest.fixture
    def solver(self):
        return SchedulerSolver()
    
    @pytest.fixture
    def base_period(self):
        return Period(id="test", name="Test", startDate=date(2025, 12, 1), endDate=date(2025, 12, 31))
    
    def test_ao_normal_distribution(self, solver, base_period):
        """Normal senaryo: 10 kişi, 28 gün, dengeli dağılım"""
        users = [create_ao_user(f"u{i}", f"User {i}") for i in range(10)]
        
        # 28 gün, her gün A+B+C (hafta içi) veya D+E+F (hafta sonu)
        slots = []
        start = date(2025, 12, 1)
        for day_offset in range(28):
            d = start + timedelta(days=day_offset)
            weekday = d.weekday()
            
            if weekday < 5:  # Hafta içi
                slots.append(create_ao_slot(f"A_{d}", d, "A", 3))
                slots.append(create_ao_slot(f"B_{d}", d, "B", 2))
                slots.append(create_ao_slot(f"C_{d}", d, "C", 1))
            else:  # Hafta sonu
                slots.append(create_ao_slot(f"D_{d}", d, "D", 2))
                slots.append(create_ao_slot(f"E_{d}", d, "E", 2))
                slots.append(create_ao_slot(f"F_{d}", d, "F", 1))
        
        request = ScheduleRequest(period=base_period, users=users, slots=slots, unavailability=[])
        response = solver.solve(request)
        
        print_distribution(response, "AÖ - Normal Dağılım (10 kişi, 28 gün)")
        
        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE")
        assert response.meta.maxShifts - response.meta.minShifts <= 3  # Max 3 fark
    
    def test_ao_wednesday_clustering(self, solver, base_period):
        """Yığılma senaryosu: Herkes Çarşamba'yı kapatmış"""
        users = [create_ao_user(f"u{i}", f"User {i}") for i in range(8)]
        
        slots = []
        unavailability = []
        start = date(2025, 12, 1)
        
        for day_offset in range(21):  # 3 hafta
            d = start + timedelta(days=day_offset)
            weekday = d.weekday()
            
            if weekday < 5:
                slots.append(create_ao_slot(f"A_{d}", d, "A", 2))
                slots.append(create_ao_slot(f"B_{d}", d, "B", 2))
                
                # Tüm Çarşambalar herkes tarafından kapatılmış
                if weekday == 2:  # Çarşamba
                    for user in users:
                        unavailability.append(Unavailability(userId=user.id, slotId=f"A_{d}"))
                        unavailability.append(Unavailability(userId=user.id, slotId=f"B_{d}"))
        
        request = ScheduleRequest(period=base_period, users=users, slots=slots, unavailability=unavailability)
        response = solver.solve(request)
        
        print_distribution(response, "AÖ - Çarşamba Yığılması (herkes kapalı)")
        
        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE")
        # Çarşambalar için unavailability violation olacak
        assert response.meta.unavailabilityViolations > 0
    
    def test_ao_night_clustering(self, solver, base_period):
        """Gece yığılması: 8 kişiden 6'sı gece kapalı"""
        users = [create_ao_user(f"u{i}", f"User {i}") for i in range(8)]
        
        slots = []
        unavailability = []
        start = date(2025, 12, 1)
        
        for day_offset in range(14):
            d = start + timedelta(days=day_offset)
            weekday = d.weekday()
            
            if weekday < 5:
                slots.append(create_ao_slot(f"C_{d}", d, "C", 1))  # Gece
                
                # İlk 6 kişi tüm geceleri kapatmış
                for i in range(6):
                    unavailability.append(Unavailability(userId=f"u{i}", slotId=f"C_{d}"))
        
        request = ScheduleRequest(period=base_period, users=users, slots=slots, unavailability=unavailability)
        response = solver.solve(request)
        
        print_distribution(response, "AÖ - Gece Yığılması (6/8 kişi kapalı)")
        
        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE")
        
        # Sadece u6 ve u7 gece alabilir
        night_users = set(a.userId for a in response.assignments)
        print(f"Gece tutan kullanıcılar: {night_users}")
    
    def test_ao_many_users_few_slots(self, solver, base_period):
        """Çok kişi az slot: 20 kişi, 10 slot"""
        users = [create_ao_user(f"u{i}", f"User {i}") for i in range(20)]
        
        slots = []
        start = date(2025, 12, 1)
        for day_offset in range(10):
            d = start + timedelta(days=day_offset)
            if d.weekday() < 5:
                slots.append(create_ao_slot(f"A_{d}", d, "A", 2))
        
        request = ScheduleRequest(period=base_period, users=users, slots=slots, unavailability=[])
        response = solver.solve(request)
        
        print_distribution(response, "AÖ - Çok Kişi Az Slot (20 kişi, ~10 slot)")
        
        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE")
        # Base = 20/20 = 1, bazı kişiler 0 alabilir
    
    def test_ao_few_users_many_slots(self, solver, base_period):
        """Az kişi çok slot: 5 kişi, 50 slot"""
        users = [create_ao_user(f"u{i}", f"User {i}") for i in range(5)]
        
        slots = []
        start = date(2025, 12, 1)
        for day_offset in range(14):
            d = start + timedelta(days=day_offset)
            if d.weekday() < 5:
                slots.append(create_ao_slot(f"A_{d}", d, "A", 3))
                slots.append(create_ao_slot(f"B_{d}", d, "B", 2))
        
        request = ScheduleRequest(period=base_period, users=users, slots=slots, unavailability=[])
        response = solver.solve(request)
        
        print_distribution(response, "AÖ - Az Kişi Çok Slot (5 kişi, çok slot)")
        
        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE")


# ============================================================================
# NA TESTS
# ============================================================================

class TestNAAlgorithm:
    """NA Algoritması Testleri"""
    
    @pytest.fixture
    def solver(self):
        return SeniorSchedulerSolver()
    
    @pytest.fixture
    def base_period(self):
        return Period(id="test", name="Test", startDate=date(2025, 12, 1), endDate=date(2025, 12, 31))
    
    def test_na_normal_distribution(self, solver, base_period):
        """Normal senaryo: 6 kişi, 20 gün (sabah+akşam)"""
        users = [create_na_user(f"na{i}", f"Senior {i}") for i in range(6)]
        
        slots = []
        start = date(2025, 12, 1)
        for day_offset in range(20):
            d = start + timedelta(days=day_offset)
            if d.weekday() < 5:  # Sadece hafta içi
                slots.append(create_na_slot(f"M_{d}", d, Segment.MORNING, 2))
                slots.append(create_na_slot(f"E_{d}", d, Segment.EVENING, 2))
        
        request = SeniorScheduleRequest(period=base_period, users=users, slots=slots, unavailability=[])
        response = solver.solve(request)
        
        print_distribution(response, "NA - Normal Dağılım (6 kişi, 20 gün)")
        
        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE")
        assert response.meta.maxShifts - response.meta.minShifts <= 3
    
    def test_na_monday_clustering(self, solver, base_period):
        """Pazartesi yığılması: Herkes Pazartesi kapalı"""
        users = [create_na_user(f"na{i}", f"Senior {i}") for i in range(5)]
        
        slots = []
        unavailability = []
        start = date(2025, 12, 1)
        
        for day_offset in range(21):
            d = start + timedelta(days=day_offset)
            if d.weekday() < 5:
                slots.append(create_na_slot(f"M_{d}", d, Segment.MORNING, 2))
                slots.append(create_na_slot(f"E_{d}", d, Segment.EVENING, 2))
                
                # Pazartesiler herkes kapalı
                if d.weekday() == 0:
                    for user in users:
                        unavailability.append(SeniorUnavailability(userId=user.id, slotId=f"M_{d}"))
                        unavailability.append(SeniorUnavailability(userId=user.id, slotId=f"E_{d}"))
        
        request = SeniorScheduleRequest(period=base_period, users=users, slots=slots, unavailability=unavailability)
        response = solver.solve(request)
        
        print_distribution(response, "NA - Pazartesi Yığılması (herkes kapalı)")
        
        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE")
        assert response.meta.unavailabilityViolations > 0
    
    def test_na_morning_preference(self, solver, base_period):
        """Sabah tercihi: Yarısı sabahı, yarısı akşamı tercih ediyor"""
        users = [
            create_na_user("na0", "Morning Lover 1", likes_morning=True),
            create_na_user("na1", "Morning Lover 2", likes_morning=True),
            create_na_user("na2", "Morning Lover 3", likes_morning=True),
            create_na_user("na3", "Evening Lover 1", likes_evening=True),
            create_na_user("na4", "Evening Lover 2", likes_evening=True),
            create_na_user("na5", "Evening Lover 3", likes_evening=True),
        ]
        
        slots = []
        start = date(2025, 12, 1)
        for day_offset in range(14):
            d = start + timedelta(days=day_offset)
            if d.weekday() < 5:
                slots.append(create_na_slot(f"M_{d}", d, Segment.MORNING, 2))
                slots.append(create_na_slot(f"E_{d}", d, Segment.EVENING, 2))
        
        request = SeniorScheduleRequest(period=base_period, users=users, slots=slots, unavailability=[])
        response = solver.solve(request)
        
        print_distribution(response, "NA - Tercih Senaryosu (3 sabahçı, 3 akşamcı)")
        
        # Tercihlere göre dağılımı analiz et
        morning_assignments = [a for a in response.assignments if "M_" in a.slotId]
        evening_assignments = [a for a in response.assignments if "E_" in a.slotId]
        
        morning_lovers_in_morning = sum(1 for a in morning_assignments if a.userId in ["na0", "na1", "na2"])
        evening_lovers_in_evening = sum(1 for a in evening_assignments if a.userId in ["na3", "na4", "na5"])
        
        print(f"Sabahçıların sabah sayısı: {morning_lovers_in_morning}/{len(morning_assignments)}")
        print(f"Akşamcıların akşam sayısı: {evening_lovers_in_evening}/{len(evening_assignments)}")
        
        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE")
    
    def test_na_desk_operator_distribution(self, solver, base_period):
        """DESK/OPERATOR dağılımı kontrolü"""
        users = [create_na_user(f"na{i}", f"Senior {i}") for i in range(4)]
        
        # 2 kişilik slotlar (1 DESK + 1 OPERATOR olmalı)
        slots = []
        start = date(2025, 12, 1)
        for day_offset in range(5):
            d = start + timedelta(days=day_offset)
            if d.weekday() < 5:
                slots.append(create_na_slot(f"M_{d}", d, Segment.MORNING, 2))
        
        request = SeniorScheduleRequest(period=base_period, users=users, slots=slots, unavailability=[])
        response = solver.solve(request)
        
        print_distribution(response, "NA - DESK/OPERATOR Dağılımı")
        
        # Her slot için 1 DESK + 1 OPERATOR olmalı
        from collections import defaultdict
        slot_roles = defaultdict(list)
        for a in response.assignments:
            slot_roles[a.slotId].append(a.seatRole.value if a.seatRole else None)
        
        print("\nSlot bazlı roller:")
        for slot_id, roles in sorted(slot_roles.items()):
            print(f"  {slot_id}: {roles}")
            if len(roles) == 2:
                assert "DESK" in roles and "OPERATOR" in roles, f"Expected 1 DESK + 1 OPERATOR, got {roles}"
        
        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE")


# ============================================================================
# STRESS TESTS
# ============================================================================

class TestStressScenarios:
    """Stres Testleri - Her iki algoritma için"""
    
    def test_ao_large_scale(self):
        """AÖ Büyük Ölçek: 25 kişi, 30 gün"""
        solver = SchedulerSolver()
        period = Period(id="test", name="Test", startDate=date(2025, 12, 1), endDate=date(2025, 12, 31))
        
        users = [create_ao_user(f"u{i}", f"User {i}") for i in range(25)]
        
        slots = []
        start = date(2025, 12, 1)
        for day_offset in range(30):
            d = start + timedelta(days=day_offset)
            weekday = d.weekday()
            
            if weekday < 5:
                slots.append(create_ao_slot(f"A_{d}", d, "A", 4))
                slots.append(create_ao_slot(f"B_{d}", d, "B", 3))
                slots.append(create_ao_slot(f"C_{d}", d, "C", 2))
            else:
                slots.append(create_ao_slot(f"D_{d}", d, "D", 3))
                slots.append(create_ao_slot(f"E_{d}", d, "E", 2))
                slots.append(create_ao_slot(f"F_{d}", d, "F", 1))
        
        request = ScheduleRequest(period=period, users=users, slots=slots, unavailability=[])
        response = solver.solve(request)
        
        print_distribution(response, "AÖ - Büyük Ölçek (25 kişi, 30 gün)")
        
        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE")
        assert response.meta.solveTimeMs < 65000  # ~60 saniye + margin
    
    def test_na_extreme_clustering(self):
        """NA Aşırı Yığılma: Herkes haftanın yarısını kapatmış"""
        solver = SeniorSchedulerSolver()
        period = Period(id="test", name="Test", startDate=date(2025, 12, 1), endDate=date(2025, 12, 31))
        
        users = [create_na_user(f"na{i}", f"Senior {i}") for i in range(8)]
        
        slots = []
        unavailability = []
        start = date(2025, 12, 1)
        
        for day_offset in range(21):
            d = start + timedelta(days=day_offset)
            if d.weekday() < 5:
                slots.append(create_na_slot(f"M_{d}", d, Segment.MORNING, 2))
                slots.append(create_na_slot(f"E_{d}", d, Segment.EVENING, 2))
                
                # Pazartesi, Salı, Çarşamba - herkes kapalı
                if d.weekday() in (0, 1, 2):
                    for user in users:
                        unavailability.append(SeniorUnavailability(userId=user.id, slotId=f"M_{d}"))
                        unavailability.append(SeniorUnavailability(userId=user.id, slotId=f"E_{d}"))
        
        request = SeniorScheduleRequest(period=period, users=users, slots=slots, unavailability=unavailability)
        response = solver.solve(request)
        
        print_distribution(response, "NA - Aşırı Yığılma (Pzt-Çar herkes kapalı)")
        
        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

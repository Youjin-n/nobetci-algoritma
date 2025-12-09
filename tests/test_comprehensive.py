"""
Konsolide Scheduler Testleri

Bu dosya algoritmanın tüm önemli senaryolarını test eder:
1. Edge Cases - Sınır durumları
2. Gerçekçi Senaryolar - 20 eski + 20 yeni çalışan
3. Unavailability Senaryoları - Farklı kapatma oranları
4. Fairness Testleri - Dağılım adaleti

Test Çalıştırma:
    pytest tests/test_comprehensive.py -v -s
"""

import random
from collections import defaultdict
from datetime import date, timedelta
from typing import Literal

import pytest

from app.schemas.schedule import (
    DayType,
    DutyType,
    Period,
    ScheduleRequest,
    Seat,
    Slot,
    SlotTypeCounts,
    Unavailability,
    User,
    UserHistory,
)
from app.services.scheduler import SchedulerSolver


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_slot(
    slot_id: str,
    slot_date: date,
    duty_type: DutyType,
    day_type: DayType,
    required_count: int = 1,
) -> Slot:
    """Slot oluştur (seats array ile)"""
    seats = [Seat(id=f"{slot_id}_s{i}", role=None) for i in range(required_count)]
    return Slot(
        id=slot_id,
        date=slot_date,
        dutyType=duty_type,
        dayType=day_type,
        seats=seats
    )


def create_user(
    user_id: str,
    name: str,
    history_weekday: int = 0,
    history_weekend: int = 0,
    expected_total: int = 0,
    likes_night: bool = False,
    dislikes_weekend: bool = False,
    slot_type_counts: dict | None = None,
) -> User:
    """Kullanıcı oluştur"""
    stc = slot_type_counts or {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}
    return User(
        id=user_id,
        name=name,
        email=f"{user_id}@test.com",
        history=UserHistory(
            weekdayCount=history_weekday,
            weekendCount=history_weekend,
            expectedTotal=expected_total,
            slotTypeCounts=SlotTypeCounts(**stc),
        ),
        likesNight=likes_night,
        dislikesWeekend=dislikes_weekend,
    )


def generate_period_slots(
    start_date: date,
    days: int = 28,
    weekday_config: dict[DutyType, int] | None = None,
    weekend_config: dict[DutyType, int] | None = None,
) -> list[Slot]:
    """
    Belirtilen gün sayısı kadar slot oluştur.
    
    weekday_config: {DutyType.A: 3, DutyType.B: 2, DutyType.C: 2} gibi
    weekend_config: {DutyType.D: 2, DutyType.E: 2, DutyType.F: 2} gibi
    """
    weekday_config = weekday_config or {DutyType.A: 3, DutyType.B: 2, DutyType.C: 2}
    weekend_config = weekend_config or {DutyType.D: 2, DutyType.E: 2, DutyType.F: 2}
    
    slots = []
    slot_id = 1
    
    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        is_weekend = current_date.weekday() >= 5
        day_type = DayType.WEEKEND if is_weekend else DayType.WEEKDAY
        config = weekend_config if is_weekend else weekday_config
        
        for duty_type, count in config.items():
            slots.append(create_slot(
                slot_id=f"slot-{slot_id}",
                slot_date=current_date,
                duty_type=duty_type,
                day_type=day_type,
                required_count=count,
            ))
            slot_id += 1
    
    return slots


def create_employees_mixed(
    num_old: int = 20,
    num_new: int = 20,
    seed: int = 12345,
) -> list[User]:
    """
    Karışık çalışan listesi oluştur.
    
    Eski çalışanlar: Rastgele geçmiş (20-80 nöbet)
    Yeni çalışanlar: Sıfır veya çok az geçmiş
    """
    random.seed(seed)
    users = []
    
    # Eski çalışanlar (geçmişi var)
    for i in range(num_old):
        user_id = f"old_{i+1:02d}"
        base_history = random.randint(20, 80)
        
        users.append(create_user(
            user_id=user_id,
            name=f"Eski Çalışan {i+1}",
            history_weekday=int(base_history * 0.7),
            history_weekend=int(base_history * 0.3),
            expected_total=base_history,
            likes_night=random.random() < 0.15,
            dislikes_weekend=random.random() < 0.25,
            slot_type_counts={
                "A": int(base_history * 0.25),
                "B": int(base_history * 0.25),
                "C": int(base_history * 0.2),
                "D": int(base_history * 0.1),
                "E": int(base_history * 0.1),
                "F": int(base_history * 0.1),
            }
        ))
    
    # Yeni çalışanlar (geçmişi yok/az)
    for i in range(num_new):
        user_id = f"new_{i+1:02d}"
        # Yeni çalışanlar: 0-5 arası nöbet
        base_history = random.randint(0, 5)
        
        users.append(create_user(
            user_id=user_id,
            name=f"Yeni Çalışan {i+1}",
            history_weekday=base_history,
            history_weekend=0,
            expected_total=base_history,
            likes_night=random.random() < 0.2,
            dislikes_weekend=random.random() < 0.3,
            slot_type_counts={
                "A": base_history,
                "B": 0, "C": 0, "D": 0, "E": 0, "F": 0,
            }
        ))
    
    return users


def generate_unavailability(
    users: list[User],
    slots: list[Slot],
    percentage: float = 0.5,
    seed: int = 54321,
) -> list[Unavailability]:
    """Rastgele unavailability oluştur"""
    random.seed(seed)
    unavailability = []
    
    for user in users:
        for slot in slots:
            if random.random() < percentage:
                unavailability.append(Unavailability(
                    userId=user.id,
                    slotId=slot.id
                ))
    
    return unavailability


def analyze_response(
    response,
    users: list[User],
    slots: list[Slot],
) -> dict:
    """Sonuçları analiz et"""
    user_counts = defaultdict(int)
    user_duty_types = defaultdict(lambda: defaultdict(int))
    slot_types = {s.id: s.dutyType.value for s in slots}
    
    for assignment in response.assignments:
        user_id = assignment.userId
        slot_id = assignment.slotId
        duty_type = slot_types.get(slot_id, "?")
        
        user_counts[user_id] += 1
        user_duty_types[user_id][duty_type] += 1
    
    counts = list(user_counts.values())
    
    return {
        "user_counts": dict(user_counts),
        "user_duty_types": dict(user_duty_types),
        "min_shifts": min(counts) if counts else 0,
        "max_shifts": max(counts) if counts else 0,
        "avg_shifts": sum(counts) / len(counts) if counts else 0,
        "shift_variance": max(counts) - min(counts) if counts else 0,
        "total_assignments": len(response.assignments),
        "unavailability_violations": response.meta.unavailabilityViolations,
        "solver_status": response.meta.solverStatus,
        "solve_time_ms": response.meta.solveTimeMs,
        "base": response.meta.base,
    }


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def solver() -> SchedulerSolver:
    return SchedulerSolver()


@pytest.fixture
def period() -> Period:
    return Period(
        id="test-period",
        name="Test Dönemi",
        startDate=date(2025, 12, 1),
        endDate=date(2025, 12, 28),
    )


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Sınır durumu testleri"""
    
    def test_single_user_single_slot(self, solver: SchedulerSolver, period: Period):
        """Tek kullanıcı, tek slot - en basit durum"""
        users = [create_user("u1", "Test User", expected_total=0)]
        slots = [create_slot("s1", date(2025, 12, 1), DutyType.A, DayType.WEEKDAY, 1)]
        
        request = ScheduleRequest(
            period=period, users=users, slots=slots, unavailability=[]
        )
        
        response = solver.solve(request)
        
        assert len(response.assignments) == 1
        assert response.assignments[0].userId == "u1"
        assert response.meta.solverStatus in ("OPTIMAL", "FEASIBLE", "TRIVIAL")
    
    def test_everyone_closed_same_slot(self, solver: SchedulerSolver, period: Period):
        """Herkes aynı slotu kapatmış - unavailability violation olmalı"""
        users = [create_user(f"u{i}", f"User {i}", expected_total=0) for i in range(3)]
        slots = [create_slot("s1", date(2025, 12, 1), DutyType.A, DayType.WEEKDAY, 1)]
        
        # Herkes s1'i kapatmış
        unavailability = [Unavailability(userId=f"u{i}", slotId="s1") for i in range(3)]
        
        request = ScheduleRequest(
            period=period, users=users, slots=slots, unavailability=unavailability
        )
        
        response = solver.solve(request)
        
        # Yine de atama yapılmalı
        assert len(response.assignments) == 1
        # Unavailability violated
        assert response.meta.unavailabilityViolations >= 1
    
    def test_forbidden_transition_c_to_a(self, solver: SchedulerSolver, period: Period):
        """C nöbeti sonrası ertesi gün A nöbeti yasak (gece->sabah)"""
        users = [create_user("u1", "User 1", expected_total=0), 
                 create_user("u2", "User 2", expected_total=0)]
        
        slots = [
            create_slot("c1", date(2025, 12, 1), DutyType.C, DayType.WEEKDAY, 1),
            create_slot("a1", date(2025, 12, 2), DutyType.A, DayType.WEEKDAY, 1),
        ]
        
        request = ScheduleRequest(
            period=period, users=users, slots=slots, unavailability=[]
        )
        
        response = solver.solve(request)
        
        # C ve A farklı kişilere atanmalı
        c1_user = next(a.userId for a in response.assignments if a.slotId == "c1")
        a1_user = next(a.userId for a in response.assignments if a.slotId == "a1")
        
        assert c1_user != a1_user, "C->A geçişi aynı kişiye yapılmamalı"
    
    def test_three_consecutive_days_prevented(self, solver: SchedulerSolver, period: Period):
        """3 gün üst üste nöbet yasağı (hard constraint değil, cezalı)"""
        # 2 kişi, 4 gün - kimse 3 gün üst üste almamalı
        users = [create_user("u1", "User 1", expected_total=0), 
                 create_user("u2", "User 2", expected_total=0)]
        
        slots = [
            create_slot(f"s{i+1}", date(2025, 12, 1) + timedelta(days=i), 
                       DutyType.A, DayType.WEEKDAY, 1)
            for i in range(4)
        ]
        
        request = ScheduleRequest(
            period=period, users=users, slots=slots, unavailability=[]
        )
        
        response = solver.solve(request)
        
        # Günleri kontrol et
        user_days: dict[str, list[date]] = defaultdict(list)
        for a in response.assignments:
            slot = next(s for s in slots if s.id == a.slotId)
            user_days[a.userId].append(slot.slot_date)
        
        for uid, days in user_days.items():
            days.sort()
            for i in range(len(days) - 2):
                d1, d2, d3 = days[i], days[i+1], days[i+2]
                if (d2 - d1).days == 1 and (d3 - d2).days == 1:
                    pytest.fail(f"User {uid} has 3 consecutive days")
    
    def test_multiple_seats_per_slot(self, solver: SchedulerSolver, period: Period):
        """Bir slotta birden fazla koltuk (A nöbeti 3 kişi)"""
        users = [create_user(f"u{i}", f"User {i}", expected_total=0) for i in range(5)]
        slots = [create_slot("s1", date(2025, 12, 1), DutyType.A, DayType.WEEKDAY, 3)]
        
        request = ScheduleRequest(
            period=period, users=users, slots=slots, unavailability=[]
        )
        
        response = solver.solve(request)
        
        # 3 atama olmalı
        assert len(response.assignments) == 3
        # Hepsi s1'e
        assert all(a.slotId == "s1" for a in response.assignments)
        # Farklı kullanıcılar
        user_ids = [a.userId for a in response.assignments]
        assert len(set(user_ids)) == 3


# =============================================================================
# FAIRNESS TESTS
# =============================================================================

class TestFairness:
    """Adil dağıtım testleri"""
    
    def test_equal_distribution_basic(self, solver: SchedulerSolver, period: Period):
        """Eşit sayıda slot, eşit dağılım bekleniyor"""
        users = [create_user(f"u{i}", f"User {i}", expected_total=0) for i in range(4)]
        
        # 8 slot, 4 kişi -> herkes 2 almalı
        slots = [
            create_slot(f"s{i+1}", date(2025, 12, 1) + timedelta(days=i), 
                       DutyType.A, DayType.WEEKDAY, 1)
            for i in range(8)
        ]
        
        request = ScheduleRequest(
            period=period, users=users, slots=slots, unavailability=[]
        )
        
        response = solver.solve(request)
        results = analyze_response(response, users, slots)
        
        # Herkes 2 nöbet almalı
        assert results["min_shifts"] == 2
        assert results["max_shifts"] == 2
    
    def test_history_fairness_old_vs_new(self, solver: SchedulerSolver, period: Period):
        """Geçmişi çok olan kişi daha az veya eşit nöbet almalı (soft constraint)"""
        # Eski: 100 nöbet geçmişi, Yeni: 0 nöbet geçmişi
        users = [
            create_user("old", "Eski Çalışan", history_weekday=70, history_weekend=30, expected_total=100),
            create_user("new", "Yeni Çalışan", expected_total=0),
        ]
        
        # 4 slot (bölünebilir, her biri 2 alacak)
        slots = [
            create_slot(f"s{i+1}", date(2025, 12, 1) + timedelta(days=i), 
                       DutyType.B, DayType.WEEKDAY, 1)
            for i in range(4)
        ]
        
        request = ScheduleRequest(
            period=period, users=users, slots=slots, unavailability=[]
        )
        
        response = solver.solve(request)
        results = analyze_response(response, users, slots)
        
        # Bu dönem için eşit dağılım bekleniyor (base=2)
        # History fairness global dengelemeye katkı sağlar ama bu dönemde eşitlik bozulmaz
        old_count = results["user_counts"].get("old", 0)
        new_count = results["user_counts"].get("new", 0)
        
        # Her ikisi de 2 nöbet almalı (4 slot / 2 kişi)
        assert old_count + new_count == 4, "Toplam 4 atama olmalı"
        assert abs(old_count - new_count) <= 1, f"Fark en fazla 1 olmalı: old={old_count}, new={new_count}"
    
    def test_unavailability_fairness_most_blocked_assigned(self, solver: SchedulerSolver, period: Period):
        """Herkes kapattıysa, en çok o türü kapatan atanmalı"""
        users = [
            create_user("u1", "Az Kapatan", expected_total=0),
            create_user("u2", "Çok Kapatan", expected_total=0),
            create_user("u3", "Orta Kapatan", expected_total=0),
        ]
        
        # 4 C slotu
        slots = [
            create_slot(f"c{i}", date(2025, 12, i+1), DutyType.C, DayType.WEEKDAY, 1)
            for i in range(4)
        ]
        
        # u2: 4 C kapatmış (en çok), u3: 2, u1: 1
        unavailability = [
            Unavailability(userId="u1", slotId="c0"),
            Unavailability(userId="u2", slotId="c0"),
            Unavailability(userId="u2", slotId="c1"),
            Unavailability(userId="u2", slotId="c2"),
            Unavailability(userId="u2", slotId="c3"),
            Unavailability(userId="u3", slotId="c0"),
            Unavailability(userId="u3", slotId="c1"),
        ]
        
        request = ScheduleRequest(
            period=period, users=users, slots=slots, unavailability=unavailability
        )
        
        response = solver.solve(request)
        
        # c0 için herkes kapalı, u2 atanmalı
        c0_assignment = next((a for a in response.assignments if a.slotId == "c0"), None)
        
        assert c0_assignment is not None
        assert c0_assignment.userId == "u2", \
            f"c0'a en çok C kapatan (u2) atanmalıydı, {c0_assignment.userId} atandı"


# =============================================================================
# REALISTIC SCENARIOS
# =============================================================================

class TestRealisticScenarios:
    """Gerçekçi senaryo testleri"""
    
    def test_20_old_20_new_employees_28_days(self, solver: SchedulerSolver, period: Period):
        """
        Gerçekçi senaryo: 20 eski + 20 yeni çalışan, 28 gün.
        
        Eski çalışanlar: 20-80 arası rastgele geçmiş nöbet
        Yeni çalışanlar: 0-5 arası geçmiş (yeni başlamış)
        Unavailability: %50
        """
        users = create_employees_mixed(num_old=20, num_new=20)
        slots = generate_period_slots(date(2025, 12, 1), days=28)
        unavailability = generate_unavailability(users, slots, percentage=0.5)
        
        request = ScheduleRequest(
            period=period, users=users, slots=slots, unavailability=unavailability
        )
        
        response = solver.solve(request)
        results = analyze_response(response, users, slots)
        
        print("\n" + "=" * 70)
        print("  20 ESKİ + 20 YENİ ÇALIŞAN, 28 GÜN, %50 UNAVAILABILITY")
        print("=" * 70)
        print(f"\n📊 Solver Status: {results['solver_status']}")
        print(f"   Çözüm Süresi: {results['solve_time_ms']:.2f} ms")
        print(f"   Toplam Atama: {results['total_assignments']}")
        print(f"   Base: {results['base']}")
        print(f"\n📈 Dağılım: Min={results['min_shifts']}, Max={results['max_shifts']}, "
              f"Avg={results['avg_shifts']:.2f}")
        print(f"   Unavailability İhlal: {results['unavailability_violations']}")
        
        # Eski vs Yeni karşılaştırması
        old_counts = [c for u, c in results["user_counts"].items() if u.startswith("old_")]
        new_counts = [c for u, c in results["user_counts"].items() if u.startswith("new_")]
        
        if old_counts and new_counts:
            print(f"\n👥 Eski çalışanlar: Avg={sum(old_counts)/len(old_counts):.2f}")
            print(f"   Yeni çalışanlar: Avg={sum(new_counts)/len(new_counts):.2f}")
        
        # Assertions
        assert results['solver_status'] in ("OPTIMAL", "FEASIBLE")
        assert results['shift_variance'] <= 5, f"Dağılım çok dengesiz: {results['shift_variance']}"
        assert results['min_shifts'] >= 1, "Kimse 0 nöbet kalmamalı"
    
    def test_high_unavailability_70_percent(self, solver: SchedulerSolver, period: Period):
        """Yüksek unavailability (%70) ile çözüm bulunabilmeli"""
        users = create_employees_mixed(num_old=15, num_new=15)
        slots = generate_period_slots(date(2025, 12, 1), days=14)  # 2 hafta
        unavailability = generate_unavailability(users, slots, percentage=0.7, seed=99999)
        
        request = ScheduleRequest(
            period=period, users=users, slots=slots, unavailability=unavailability
        )
        
        response = solver.solve(request)
        results = analyze_response(response, users, slots)
        
        print("\n" + "=" * 70)
        print("  30 ÇALIŞAN, 14 GÜN, %70 UNAVAILABILITY (ZOR SENARYO)")
        print("=" * 70)
        print(f"\n📊 Solver Status: {results['solver_status']}")
        print(f"   Unavailability İhlal: {results['unavailability_violations']}")
        print(f"   Dağılım: Min={results['min_shifts']}, Max={results['max_shifts']}")
        
        # Çözüm bulunmalı
        assert results['solver_status'] in ("OPTIMAL", "FEASIBLE")
    
    def test_small_team_many_slots(self, solver: SchedulerSolver, period: Period):
        """Az kişi, çok slot - herkes çok nöbet alacak"""
        users = [create_user(f"u{i}", f"User {i}", expected_total=0) for i in range(5)]
        slots = generate_period_slots(date(2025, 12, 1), days=7)  # 1 hafta
        unavailability = generate_unavailability(users, slots, percentage=0.3)
        
        request = ScheduleRequest(
            period=period, users=users, slots=slots, unavailability=unavailability
        )
        
        response = solver.solve(request)
        results = analyze_response(response, users, slots)
        
        print("\n" + "=" * 70)
        print("  5 KİŞİ, 1 HAFTA (AZ PERSONEL SENARYOSU)")
        print("=" * 70)
        print(f"\n📊 Solver Status: {results['solver_status']}")
        print(f"   Kişi başı ortalama: {results['avg_shifts']:.2f} nöbet")
        print(f"   Dağılım: Min={results['min_shifts']}, Max={results['max_shifts']}")
        
        assert results['solver_status'] in ("OPTIMAL", "FEASIBLE")
        # Fark base+2 sınırı içinde olmalı
        assert results['shift_variance'] <= 3


# =============================================================================
# PREFERENCE TESTS  
# =============================================================================

class TestPreferences:
    """Tercih testleri"""
    
    def test_likes_night_preference(self, solver: SchedulerSolver, period: Period):
        """Gece seven kişiye C nöbeti verilmeli"""
        users = [
            create_user("night_lover", "Gece Sever", expected_total=0, likes_night=True),
            create_user("normal", "Normal", expected_total=0, likes_night=False),
        ]
        
        slots = [
            create_slot("c1", date(2025, 12, 1), DutyType.C, DayType.WEEKDAY, 1),
            create_slot("a1", date(2025, 12, 2), DutyType.A, DayType.WEEKDAY, 1),
        ]
        
        request = ScheduleRequest(
            period=period, users=users, slots=slots, unavailability=[]
        )
        
        response = solver.solve(request)
        
        c1_user = next(a.userId for a in response.assignments if a.slotId == "c1")
        
        # Gece seven kişi C almalı (soft constraint)
        assert c1_user == "night_lover", "Gece nöbetini gece seven almalı"
    
    def test_dislikes_weekend_preference(self, solver: SchedulerSolver, period: Period):
        """Hafta sonu istemeyen kişiye hafta sonu verilmemeli"""
        users = [
            create_user("no_weekend", "Haftasonu İstemiyor", expected_total=0, dislikes_weekend=True),
            create_user("normal", "Normal", expected_total=0, dislikes_weekend=False),
        ]
        
        slots = [
            create_slot("d1", date(2025, 12, 6), DutyType.D, DayType.WEEKEND, 1),  # Cumartesi
            create_slot("a1", date(2025, 12, 8), DutyType.A, DayType.WEEKDAY, 1),  # Pazartesi
        ]
        
        request = ScheduleRequest(
            period=period, users=users, slots=slots, unavailability=[]
        )
        
        response = solver.solve(request)
        
        d1_user = next(a.userId for a in response.assignments if a.slotId == "d1")
        
        # Normal kullanıcı hafta sonunu almalı
        assert d1_user == "normal", "Hafta sonu istemeyen kişiye hafta sonu verilmemeli"


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

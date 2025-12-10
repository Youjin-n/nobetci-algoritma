"""
Realistic Large-Scale Test Scenarios with JSON Output

Bu script gerçekçi büyük ölçekli senaryolar oluşturur ve:
1. API'ye giden JSON request'leri kaydeder
2. API'den dönen JSON response'ları kaydeder
3. Algoritma istatistiklerini kaydeder
"""

import json
import os
from datetime import date, timedelta
from pathlib import Path

from app.services.scheduler.solver import SchedulerSolver
from app.services.scheduler.senior_solver import SeniorSchedulerSolver
from app.schemas.schedule import (
    ScheduleRequest, User, Slot, Unavailability, Period, UserHistory, Seat, SlotTypeCounts, DayType
)
from app.schemas.schedule_senior import (
    SeniorScheduleRequest, SeniorUser, SeniorSlot, SeniorUserHistory, SeniorSeat, 
    SeniorUnavailability, Segment
)

# Output directory
OUTPUT_DIR = Path("test_outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


def save_json(data: dict, filename: str):
    """JSON dosyasına kaydet"""
    filepath = OUTPUT_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"  Saved: {filepath}")


def create_ao_user(user_id: str, name: str, likes_night: bool = False, dislikes_weekend: bool = False) -> User:
    """AÖ kullanıcısı oluştur"""
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
    day_type = DayType.WEEKEND if duty_type in ("D", "E", "F") else DayType.WEEKDAY
    seats = [Seat(id=f"{slot_id}_s{i}", role=None) for i in range(seat_count)]
    return Slot(id=slot_id, date=slot_date, dutyType=duty_type, dayType=day_type, seats=seats)


def create_na_user(user_id: str, name: str, likes_morning: bool = False, likes_evening: bool = False) -> SeniorUser:
    """NA kullanıcısı oluştur"""
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


def analyze_response(response, label: str) -> dict:
    """Response analizi yap"""
    user_counts = {}
    for a in response.assignments:
        user_counts[a.userId] = user_counts.get(a.userId, 0) + 1
    
    counts = list(user_counts.values()) if user_counts else [0]
    
    return {
        "scenario": label,
        "solver_status": response.meta.solverStatus,
        "base": response.meta.base,
        "min_shifts": response.meta.minShifts,
        "max_shifts": response.meta.maxShifts,
        "shift_variance": max(counts) - min(counts) if counts else 0,
        "total_slots": response.meta.totalSlots,
        "total_assignments": response.meta.totalAssignments,
        "unavailability_violations": response.meta.unavailabilityViolations,
        "users_at_base_plus_2": response.meta.usersAtBasePlus2,
        "solve_time_ms": round(response.meta.solveTimeMs, 2),
        "warnings": response.meta.warnings,
        "user_distribution": user_counts
    }


# ============================================================================
# SCENARIO 1: AÖ - Gerçekçi Hastane Senaryosu (25 kişi, 28 gün)
# ============================================================================

def run_ao_realistic_hospital():
    """
    Gerçekçi hastane senaryosu:
    - 25 asistan öğrenci
    - 28 günlük dönem
    - Her gün A/B/C veya D/E/F
    - Rastgele yığılmalar (Çarşamba ve Cuma çok kapalı)
    """
    print("\n" + "="*70)
    print("AÖ - Gerçekçi Hastane Senaryosu (25 kişi, 28 gün)")
    print("="*70)
    
    solver = SchedulerSolver()
    period = Period(id="dec-2025", name="Aralık 2025", startDate=date(2025, 12, 1), endDate=date(2025, 12, 28))
    
    # 25 kullanıcı - bazıları tercihli
    users = []
    for i in range(25):
        likes_night = i % 5 == 0  # Her 5. kişi gece sever
        dislikes_weekend = i % 4 == 0  # Her 4. kişi hafta sonu sevmez
        users.append(create_ao_user(f"ao_{i:02d}", f"Asistan {i+1}", likes_night, dislikes_weekend))
    
    # 28 gün slot
    slots = []
    start = date(2025, 12, 1)
    for day_offset in range(28):
        d = start + timedelta(days=day_offset)
        weekday = d.weekday()
        
        if weekday < 5:  # Hafta içi
            slots.append(create_ao_slot(f"A_{d}", d, "A", 4))  # 4 kişi gündüz
            slots.append(create_ao_slot(f"B_{d}", d, "B", 3))  # 3 kişi akşam
            slots.append(create_ao_slot(f"C_{d}", d, "C", 2))  # 2 kişi gece
        else:  # Hafta sonu
            slots.append(create_ao_slot(f"D_{d}", d, "D", 3))
            slots.append(create_ao_slot(f"E_{d}", d, "E", 2))
            slots.append(create_ao_slot(f"F_{d}", d, "F", 1))
    
    # Yığılmalı unavailability
    unavailability = []
    for day_offset in range(28):
        d = start + timedelta(days=day_offset)
        weekday = d.weekday()
        
        # Çarşamba (2) - çoğu kişi kapalı
        if weekday == 2:
            for i in range(20):  # 20/25 kişi kapalı
                unavailability.append(Unavailability(userId=f"ao_{i:02d}", slotId=f"A_{d}"))
                unavailability.append(Unavailability(userId=f"ao_{i:02d}", slotId=f"B_{d}"))
        
        # Cuma akşam/gece - çok kapalı
        if weekday == 4:
            for i in range(15):  # 15 kişi kapalı
                unavailability.append(Unavailability(userId=f"ao_{i:02d}", slotId=f"B_{d}"))
                unavailability.append(Unavailability(userId=f"ao_{i:02d}", slotId=f"C_{d}"))
        
        # Cumartesi - herkes hafta sonunu kapamak istiyor
        if weekday == 5:
            for i in range(18):
                unavailability.append(Unavailability(userId=f"ao_{i:02d}", slotId=f"D_{d}"))
                unavailability.append(Unavailability(userId=f"ao_{i:02d}", slotId=f"E_{d}"))
    
    request = ScheduleRequest(period=period, users=users, slots=slots, unavailability=unavailability)
    
    # Request'i kaydet
    request_dict = request.model_dump(mode="json")
    save_json(request_dict, "ao_realistic_request.json")
    
    # Çöz
    print("  Solving...")
    response = solver.solve(request)
    
    # Response'u kaydet
    response_dict = response.model_dump(mode="json")
    save_json(response_dict, "ao_realistic_response.json")
    
    # Analiz
    stats = analyze_response(response, "AÖ - Gerçekçi Hastane")
    return stats


# ============================================================================
# SCENARIO 2: NA - Gerçekçi Poliklinik Senaryosu (10 kişi, 21 gün)
# ============================================================================

def run_na_realistic_polyclinic():
    """
    Gerçekçi poliklinik senaryosu:
    - 10 nöbetçi asistan
    - 21 günlük dönem (sadece hafta içi)
    - Her gün MORNING + EVENING
    - Pazartesi ve Salı yığılma
    """
    print("\n" + "="*70)
    print("NA - Gerçekçi Poliklinik Senaryosu (10 kişi, 21 gün)")
    print("="*70)
    
    solver = SeniorSchedulerSolver()
    period = Period(id="dec-2025", name="Aralık 2025", startDate=date(2025, 12, 1), endDate=date(2025, 12, 21))
    
    # 10 kullanıcı
    users = []
    for i in range(10):
        likes_morning = i < 5  # İlk 5 kişi sabahçı
        likes_evening = i >= 5  # Son 5 kişi akşamcı
        users.append(create_na_user(f"na_{i:02d}", f"NA {i+1}", likes_morning, likes_evening))
    
    # 21 gün slot (sadece hafta içi)
    slots = []
    unavailability = []
    start = date(2025, 12, 1)
    
    day_count = 0
    day_offset = 0
    while day_count < 21:
        d = start + timedelta(days=day_offset)
        day_offset += 1
        
        if d.weekday() >= 5:  # Hafta sonu atla
            continue
        
        day_count += 1
        slots.append(create_na_slot(f"M_{d}", d, Segment.MORNING, 2))
        slots.append(create_na_slot(f"E_{d}", d, Segment.EVENING, 2))
        
        # Pazartesi - herkes kapalı (yığılma)
        if d.weekday() == 0:
            for i in range(8):  # 8/10 kişi kapalı
                unavailability.append(SeniorUnavailability(userId=f"na_{i:02d}", slotId=f"M_{d}"))
                unavailability.append(SeniorUnavailability(userId=f"na_{i:02d}", slotId=f"E_{d}"))
        
        # Salı sabah - çok kapalı
        if d.weekday() == 1:
            for i in range(6):
                unavailability.append(SeniorUnavailability(userId=f"na_{i:02d}", slotId=f"M_{d}"))
    
    request = SeniorScheduleRequest(period=period, users=users, slots=slots, unavailability=unavailability)
    
    # Request'i kaydet
    request_dict = request.model_dump(mode="json")
    save_json(request_dict, "na_realistic_request.json")
    
    # Çöz
    print("  Solving...")
    response = solver.solve(request)
    
    # Response'u kaydet
    response_dict = response.model_dump(mode="json")
    save_json(response_dict, "na_realistic_response.json")
    
    # Analiz
    stats = analyze_response(response, "NA - Gerçekçi Poliklinik")
    return stats


# ============================================================================
# SCENARIO 3: AÖ - Aşırı Yığılma Senaryosu
# ============================================================================

def run_ao_extreme_clustering():
    """
    Aşırı yığılma senaryosu:
    - 20 kişi
    - Herkes hafta içi tüm geceleri kapatmış
    - Herkes Cumartesi kapatmış
    """
    print("\n" + "="*70)
    print("AÖ - Aşırı Yığılma Senaryosu")
    print("="*70)
    
    solver = SchedulerSolver()
    period = Period(id="dec-2025", name="Aralık 2025", startDate=date(2025, 12, 1), endDate=date(2025, 12, 14))
    
    users = [create_ao_user(f"ao_{i:02d}", f"Asistan {i+1}") for i in range(20)]
    
    slots = []
    unavailability = []
    start = date(2025, 12, 1)
    
    for day_offset in range(14):
        d = start + timedelta(days=day_offset)
        weekday = d.weekday()
        
        if weekday < 5:
            slots.append(create_ao_slot(f"A_{d}", d, "A", 3))
            slots.append(create_ao_slot(f"B_{d}", d, "B", 2))
            slots.append(create_ao_slot(f"C_{d}", d, "C", 2))
            
            # HERKES gece kapalı
            for user in users:
                unavailability.append(Unavailability(userId=user.id, slotId=f"C_{d}"))
        else:
            slots.append(create_ao_slot(f"D_{d}", d, "D", 2))
            slots.append(create_ao_slot(f"E_{d}", d, "E", 2))
            slots.append(create_ao_slot(f"F_{d}", d, "F", 1))
            
            # Cumartesi HERKES kapalı
            if weekday == 5:
                for user in users:
                    unavailability.append(Unavailability(userId=user.id, slotId=f"D_{d}"))
                    unavailability.append(Unavailability(userId=user.id, slotId=f"E_{d}"))
    
    request = ScheduleRequest(period=period, users=users, slots=slots, unavailability=unavailability)
    
    request_dict = request.model_dump(mode="json")
    save_json(request_dict, "ao_extreme_request.json")
    
    print("  Solving...")
    response = solver.solve(request)
    
    response_dict = response.model_dump(mode="json")
    save_json(response_dict, "ao_extreme_response.json")
    
    stats = analyze_response(response, "AÖ - Aşırı Yığılma")
    return stats


# ============================================================================
# SCENARIO 4: NA - Aşırı Yığılma Senaryosu
# ============================================================================

def run_na_extreme_clustering():
    """
    NA aşırı yığılma:
    - 8 kişi
    - Pazartesi-Çarşamba HERKES kapalı
    """
    print("\n" + "="*70)
    print("NA - Aşırı Yığılma Senaryosu")
    print("="*70)
    
    solver = SeniorSchedulerSolver()
    period = Period(id="dec-2025", name="Aralık 2025", startDate=date(2025, 12, 1), endDate=date(2025, 12, 14))
    
    users = [create_na_user(f"na_{i:02d}", f"NA {i+1}") for i in range(8)]
    
    slots = []
    unavailability = []
    start = date(2025, 12, 1)
    
    for day_offset in range(14):
        d = start + timedelta(days=day_offset)
        if d.weekday() >= 5:
            continue
        
        slots.append(create_na_slot(f"M_{d}", d, Segment.MORNING, 2))
        slots.append(create_na_slot(f"E_{d}", d, Segment.EVENING, 2))
        
        # Pazartesi-Çarşamba HERKES kapalı
        if d.weekday() in (0, 1, 2):
            for user in users:
                unavailability.append(SeniorUnavailability(userId=user.id, slotId=f"M_{d}"))
                unavailability.append(SeniorUnavailability(userId=user.id, slotId=f"E_{d}"))
    
    request = SeniorScheduleRequest(period=period, users=users, slots=slots, unavailability=unavailability)
    
    request_dict = request.model_dump(mode="json")
    save_json(request_dict, "na_extreme_request.json")
    
    print("  Solving...")
    response = solver.solve(request)
    
    response_dict = response.model_dump(mode="json")
    save_json(response_dict, "na_extreme_response.json")
    
    stats = analyze_response(response, "NA - Aşırı Yığılma")
    return stats


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "="*70)
    print("BÜYÜK ÖLÇEKLİ GERÇEKÇİ SENARYO TESTLERİ")
    print("="*70)
    print(f"Output directory: {OUTPUT_DIR.absolute()}")
    
    all_stats = []
    
    # Run all scenarios
    all_stats.append(run_ao_realistic_hospital())
    all_stats.append(run_na_realistic_polyclinic())
    all_stats.append(run_ao_extreme_clustering())
    all_stats.append(run_na_extreme_clustering())
    
    # Save combined stats
    save_json(all_stats, "all_statistics.json")
    
    # Print summary
    print("\n" + "="*70)
    print("ÖZET İSTATİSTİKLER")
    print("="*70)
    
    for stats in all_stats:
        print(f"\n{stats['scenario']}:")
        print(f"  Status: {stats['solver_status']}")
        print(f"  Base: {stats['base']}, Range: {stats['min_shifts']}-{stats['max_shifts']}")
        print(f"  Unavailability Violations: {stats['unavailability_violations']}")
        print(f"  Solve Time: {stats['solve_time_ms']}ms")
        if stats['warnings']:
            print(f"  Warnings: {stats['warnings']}")
    
    # Create readable summary file
    summary_lines = [
        "=" * 70,
        "ALGORİTMA TEST SONUÇLARI",
        "=" * 70,
        "",
    ]
    
    for stats in all_stats:
        summary_lines.extend([
            f"## {stats['scenario']}",
            f"",
            f"| Metrik | Değer |",
            f"|--------|-------|",
            f"| Status | {stats['solver_status']} |",
            f"| Base | {stats['base']} |",
            f"| Min/Max | {stats['min_shifts']}/{stats['max_shifts']} |",
            f"| Fark | {stats['shift_variance']} |",
            f"| Toplam Slot | {stats['total_slots']} |",
            f"| Toplam Atama | {stats['total_assignments']} |",
            f"| Unavailability Violation | {stats['unavailability_violations']} |",
            f"| Base+2'ye Ulaşan | {stats['users_at_base_plus_2']} |",
            f"| Çözüm Süresi | {stats['solve_time_ms']}ms |",
            f"",
            f"Kullanıcı Dağılımı:",
        ])
        for uid, count in sorted(stats['user_distribution'].items()):
            summary_lines.append(f"  {uid}: {count} nöbet")
        summary_lines.append("")
        if stats['warnings']:
            summary_lines.append(f"Warnings: {', '.join(stats['warnings'])}")
        summary_lines.append("-" * 70)
        summary_lines.append("")
    
    with open(OUTPUT_DIR / "SUMMARY.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))
    print(f"\nSummary saved to: {OUTPUT_DIR / 'SUMMARY.txt'}")
    
    print("\n" + "="*70)
    print("TÜM DOSYALAR KAYDEDILDI:")
    print("="*70)
    for f in sorted(OUTPUT_DIR.iterdir()):
        print(f"  {f.name}")


if __name__ == "__main__":
    main()

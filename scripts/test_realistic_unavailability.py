"""
Gerçekçi Unavailability Test Script

26 kullanıcı, farklı kapatma desenleri:
- 5 kişi: Pazartesi-Çarşamba-Cuma kapalı (ders var)
- 3 kişi: Salı-Perşembe kapalı (ders var)
- 4 kişi: Hafta sonları kapalı (aileye gidiyor)
- 3 kişi: %80+ slot kapalı (çok meşgul)
- 5 kişi: %50 rastgele kapalı
- 4 kişi: Sadece geceler kapalı (gece çalışamıyor)
- 2 kişi: Hiç kapatmadı (tam müsait)
"""

import sys
import random
from datetime import date, timedelta

sys.path.insert(0, ".")

from app.services.scheduler.solver import SchedulerSolver
from app.schemas.schedule import (
    ScheduleRequest, Period, User, UserHistory, Slot, Seat, Unavailability
)


def create_user(idx: int) -> dict:
    """Standard user with zero history"""
    return {
        "id": f"u{idx:02d}",
        "name": f"User{idx:02d}",
        "email": f"user{idx:02d}@test.com",
        "likesNight": False,
        "dislikesWeekend": False,
        "history": {
            "totalAllTime": 0, "expectedTotal": 0,
            "weekdayCount": 0, "weekendCount": 0,
            "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0,
            "countNightAllTime": 0, "countWeekendAllTime": 0,
            "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}
        }
    }


def create_slots(period_start: date, period_end: date) -> list[dict]:
    """Create all slots for the period"""
    slots = []
    slot_id = 0
    current = period_start
    
    while current <= period_end:
        is_weekend = current.weekday() >= 5
        dt_str = current.isoformat()
        
        if is_weekend:
            # Weekend: D (08:00-16:00), E (16:00-23:30), F (23:30-08:00)
            for duty, count in [("D", 2), ("E", 2), ("F", 2)]:
                seats = [{"id": f"s{slot_id}_{j}", "role": None} for j in range(count)]
                slots.append({
                    "id": f"slot{slot_id}", "date": dt_str, "dutyType": duty,
                    "dayType": "WEEKEND", "seats": seats
                })
                slot_id += 1
        else:
            # Weekday: A (08:30-17:30), B (17:30-23:30), C (23:30-08:30)
            for duty, count in [("A", 3), ("B", 2), ("C", 2)]:
                seats = [{"id": f"s{slot_id}_{j}", "role": None} for j in range(count)]
                slots.append({
                    "id": f"slot{slot_id}", "date": dt_str, "dutyType": duty,
                    "dayType": "WEEKDAY", "seats": seats
                })
                slot_id += 1
        
        current += timedelta(days=1)
    
    return slots


def generate_unavailability(users: list[dict], slots: list[dict]) -> list[dict]:
    """Generate realistic unavailability patterns"""
    unavailability = []
    
    # Parse slot dates
    slot_dates = {}
    for slot in slots:
        slot_dates[slot["id"]] = {
            "date": date.fromisoformat(slot["date"]),
            "duty": slot["dutyType"],
            "day_type": slot["dayType"]
        }
    
    for user_idx, user in enumerate(users):
        user_id = user["id"]
        
        # Pattern based on user index
        if user_idx < 5:
            # 5 kişi: Pazartesi-Çarşamba-Cuma kapalı (ders var)
            for slot in slots:
                slot_date = date.fromisoformat(slot["date"])
                if slot_date.weekday() in [0, 2, 4]:  # Pzt, Çar, Cum
                    unavailability.append({"userId": user_id, "slotId": slot["id"]})
                    
        elif user_idx < 8:
            # 3 kişi: Salı-Perşembe kapalı
            for slot in slots:
                slot_date = date.fromisoformat(slot["date"])
                if slot_date.weekday() in [1, 3]:  # Sal, Per
                    unavailability.append({"userId": user_id, "slotId": slot["id"]})
                    
        elif user_idx < 12:
            # 4 kişi: Hafta sonları kapalı
            for slot in slots:
                if slot["dayType"] == "WEEKEND":
                    unavailability.append({"userId": user_id, "slotId": slot["id"]})
                    
        elif user_idx < 15:
            # 3 kişi: %80+ slot kapalı (çok meşgul)
            random.seed(user_idx * 1000)
            for slot in slots:
                if random.random() < 0.80:
                    unavailability.append({"userId": user_id, "slotId": slot["id"]})
                    
        elif user_idx < 20:
            # 5 kişi: %50 rastgele kapalı
            random.seed(user_idx * 1000)
            for slot in slots:
                if random.random() < 0.50:
                    unavailability.append({"userId": user_id, "slotId": slot["id"]})
                    
        elif user_idx < 24:
            # 4 kişi: Sadece geceler kapalı (C ve F)
            for slot in slots:
                if slot["dutyType"] in ["C", "F"]:
                    unavailability.append({"userId": user_id, "slotId": slot["id"]})
                    
        # else: 2 kişi hiç kapatmadı (user 24, 25)
    
    return unavailability


def main():
    print("=" * 80)
    print("GERÇEKÇİ UNAVAILABILITY TESTİ")
    print("=" * 80)
    
    # Period: 15 Aralık 2025 - 25 Ocak 2026 (42 gün)
    period_start = date(2025, 12, 15)
    period_end = date(2026, 1, 25)
    
    # Create 26 users
    users = [create_user(i) for i in range(26)]
    
    # Create slots
    slots = create_slots(period_start, period_end)
    
    # Generate unavailability
    unavailability = generate_unavailability(users, slots)
    
    # Stats
    total_slots = len(slots)
    total_seats = sum(len(s["seats"]) for s in slots)
    
    print(f"\nKONFİGÜRASYON:")
    print(f"  Dönem: {period_start} - {period_end}")
    print(f"  Kullanıcı: {len(users)}")
    print(f"  Slot: {total_slots}")
    print(f"  Toplam Koltuk: {total_seats}")
    print(f"  Unavailability: {len(unavailability)}")
    
    # Per-user unavailability count
    user_unavail = {}
    for u in unavailability:
        user_unavail[u["userId"]] = user_unavail.get(u["userId"], 0) + 1
    
    print(f"\nKAVAPITMA DAĞILIMI (slot sayısı / {total_slots} = %):")
    for uid, count in sorted(user_unavail.items(), key=lambda x: x[1], reverse=True):
        pct = count / total_slots * 100
        print(f"  {uid}: {count:3d} slot ({pct:5.1f}%)")
    
    # Count users with 0 unavailability
    zero_unavail = [u["id"] for u in users if u["id"] not in user_unavail]
    print(f"\nHİÇ KAPATMAYAN: {zero_unavail}")
    
    # Build request
    request = {
        "period": {
            "id": "p1",
            "name": "Gerçekçi Test",
            "startDate": period_start.isoformat(),
            "endDate": period_end.isoformat()
        },
        "users": users,
        "slots": slots,
        "unavailability": unavailability
    }
    
    print(f"\nÇözülüyor...")
    
    # Solve
    result = SchedulerSolver().solve(ScheduleRequest(**request))
    
    print(f"\n{'=' * 80}")
    print("SONUÇLAR")
    print(f"{'=' * 80}")
    
    print(f"\nMeta: Status={result.meta.solverStatus}, Min={result.meta.minShifts}, Max={result.meta.maxShifts}")
    print(f"Unavailability Violations: {result.meta.unavailabilityViolations}")
    
    # Collect per-user stats
    user_stats = {u["id"]: {"total": 0, "A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0, "unavail_closed": user_unavail.get(u["id"], 0)} for u in users}
    
    # Map slot_id to duty_type
    slot_duty = {s["id"]: s["dutyType"] for s in slots}
    
    for assignment in result.assignments:
        uid = assignment.userId
        duty = slot_duty.get(assignment.slotId, "?")
        user_stats[uid]["total"] += 1
        if duty in user_stats[uid]:
            user_stats[uid][duty] += 1
    
    # Print table
    print(f"\n{'User':<8} {'Total':>5} {'A':>4} {'B':>4} {'C':>4} {'D':>4} {'E':>4} {'F':>4} {'Kapalı%':>8}")
    print("-" * 60)
    
    for uid in sorted(user_stats.keys()):
        stats = user_stats[uid]
        pct = stats["unavail_closed"] / total_slots * 100
        print(f"{uid:<8} {stats['total']:>5} {stats['A']:>4} {stats['B']:>4} {stats['C']:>4} {stats['D']:>4} {stats['E']:>4} {stats['F']:>4} {pct:>7.1f}%")
    
    # Summary
    print(f"\n{'=' * 80}")
    print("ÖZET")
    print(f"{'=' * 80}")
    
    totals = [s["total"] for s in user_stats.values()]
    print(f"Toplam: min={min(totals)}, max={max(totals)}, fark={max(totals)-min(totals)}")
    
    # Check if heavily closing users got assigned to unavailable slots
    print(f"\nUnavailability Violations: {result.meta.unavailabilityViolations}")


if __name__ == "__main__":
    main()

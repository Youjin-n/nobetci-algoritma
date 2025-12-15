"""
Test to debug fairness with exact user scenario - all new users, no history.
"""
import json
from datetime import date, timedelta
from collections import defaultdict

from app.services.scheduler.solver import SchedulerSolver
from app.schemas.schedule import (
    ScheduleRequest, User, Slot, Unavailability, Period, UserHistory, Seat, SlotTypeCounts, DayType
)


def create_new_user(user_id: str, name: str) -> User:
    """YENİ kullanıcı - tüm history 0"""
    return User(
        id=user_id,
        name=name,
        likesNight=False,
        dislikesWeekend=False,
        history=UserHistory(
            weekdayCount=0,
            weekendCount=0,
            expectedTotal=0,  # ← ÖNEMLİ: 0 olmalı
            slotTypeCounts=SlotTypeCounts(A=0, B=0, C=0, D=0, E=0, F=0)
        )
    )


def create_weekday_slots(slot_date: date) -> list[Slot]:
    """Hafta içi: A(4 kişi), B(2 kişi), C(2 kişi) = 8 koltuk/gün"""
    date_str = slot_date.isoformat()
    return [
        Slot(id=f"A_{date_str}", date=slot_date, dutyType="A", dayType=DayType.WEEKDAY,
             seats=[Seat(id=f"A_{date_str}_s{i}", role=None) for i in range(4)]),
        Slot(id=f"B_{date_str}", date=slot_date, dutyType="B", dayType=DayType.WEEKDAY,
             seats=[Seat(id=f"B_{date_str}_s{i}", role=None) for i in range(2)]),
        Slot(id=f"C_{date_str}", date=slot_date, dutyType="C", dayType=DayType.WEEKDAY,
             seats=[Seat(id=f"C_{date_str}_s{i}", role=None) for i in range(2)]),
    ]


def create_weekend_slots(slot_date: date) -> list[Slot]:
    """Hafta sonu: D(2 kişi), E(2 kişi), F(1 kişi) = 5 koltuk/gün"""
    date_str = slot_date.isoformat()
    return [
        Slot(id=f"D_{date_str}", date=slot_date, dutyType="D", dayType=DayType.WEEKEND,
             seats=[Seat(id=f"D_{date_str}_s{i}", role=None) for i in range(2)]),
        Slot(id=f"E_{date_str}", date=slot_date, dutyType="E", dayType=DayType.WEEKEND,
             seats=[Seat(id=f"E_{date_str}_s{i}", role=None) for i in range(2)]),
        Slot(id=f"F_{date_str}", date=slot_date, dutyType="F", dayType=DayType.WEEKEND,
             seats=[Seat(id=f"F_{date_str}_s{i}", role=None) for i in range(1)]),
    ]


def main():
    print("="*80)
    print("GERÇEK SENARYO TESTİ - 26 YENİ KULLANICI, 28 GÜN, HİÇ UNAVAILABILITY")
    print("="*80)
    
    solver = SchedulerSolver()
    
    # 26 kullanıcı - HEPSİ YENİ (history = 0)
    users = [create_new_user(f"u{i:02d}", f"User {i+1}") for i in range(26)]
    
    # 28 gün (15 Aralık - 11 Ocak = 28 gün)
    start = date(2025, 12, 15)
    slots = []
    
    weekday_count = 0
    weekend_count = 0
    
    for day_offset in range(28):
        d = start + timedelta(days=day_offset)
        if d.weekday() < 5:
            slots.extend(create_weekday_slots(d))
            weekday_count += 1
        else:
            slots.extend(create_weekend_slots(d))
            weekend_count += 1
    
    period = Period(id="test", name="Test", startDate=start, endDate=start + timedelta(days=27))
    request = ScheduleRequest(period=period, users=users, slots=slots, unavailability=[])
    
    total_seats = sum(len(s.seats) for s in slots)
    
    print(f"\nSENARYO DETAYLARI:")
    print(f"  Hafta içi gün: {weekday_count} (×8 koltuk = {weekday_count * 8})")
    print(f"  Hafta sonu gün: {weekend_count} (×5 koltuk = {weekend_count * 5})")
    print(f"  Toplam koltuk: {total_seats}")
    print(f"  Kullanıcı: {len(users)}")
    print(f"  Kişi başı ideal: {total_seats / len(users):.2f}")
    print(f"  Base (floor): {total_seats // len(users)}")
    
    # History kontrolü
    print(f"\nHISTORY KONTROLÜ:")
    for u in users[:3]:
        print(f"  {u.name}: totalAllTime={u.history.totalAllTime}, expectedTotal={u.history.expectedTotal}")
    
    print("\nÇözülüyor...")
    response = solver.solve(request)
    
    print(f"\n{'='*80}")
    print("SONUÇLAR")
    print(f"{'='*80}")
    print(f"Status: {response.meta.solverStatus}")
    print(f"Base: {response.meta.base}")
    print(f"Min/Max: {response.meta.minShifts}/{response.meta.maxShifts}")
    print(f"Fark: {response.meta.maxShifts - response.meta.minShifts}")
    
    # Kullanıcı bazında detay
    user_stats = defaultdict(lambda: {"total": 0, "A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0})
    
    for a in response.assignments:
        user_stats[a.userId]["total"] += 1
        duty_type = a.slotId.split("_")[0]
        user_stats[a.userId][duty_type] += 1
    
    print(f"\nDETAYLI DAĞILIM:")
    print(f"{'User':<8} {'Total':<6} {'A':<4} {'B':<4} {'C':<4} {'D':<4} {'E':<4} {'F':<4}")
    print("-"*50)
    
    totals = []
    for uid in sorted(user_stats.keys()):
        s = user_stats[uid]
        print(f"{uid:<8} {s['total']:<6} {s['A']:<4} {s['B']:<4} {s['C']:<4} {s['D']:<4} {s['E']:<4} {s['F']:<4}")
        totals.append(s['total'])
    
    print(f"\nÖZET:")
    print(f"  Min: {min(totals)}, Max: {max(totals)}, Fark: {max(totals) - min(totals)}")
    
    from collections import Counter
    dist = Counter(totals)
    print(f"  Dağılım: {dict(sorted(dist.items()))}")
    
    if max(totals) - min(totals) > 2:
        print(f"\n❌ HATA! Fark 2'yi geçiyor - adalet sorunu var!")
    else:
        print(f"\n✅ Adalet sağlandı (fark ≤ 2)")


if __name__ == "__main__":
    main()

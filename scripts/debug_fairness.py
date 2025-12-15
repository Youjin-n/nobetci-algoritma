"""
Test to debug fairness distribution bug.

Senaryo: Hiç unavailability yok, herkes eşit durumda
Beklenti: Herkes eşit veya ±1 farkla nöbet almalı
"""
import json
from datetime import date, timedelta
from collections import defaultdict

from app.services.scheduler.solver import SchedulerSolver
from app.schemas.schedule import (
    ScheduleRequest, User, Slot, Unavailability, Period, UserHistory, Seat, SlotTypeCounts, DayType
)


def create_user(user_id: str, name: str) -> User:
    """Yeni kullanıcı - hiç history yok, hiç tercih yok"""
    return User(
        id=user_id,
        name=name,
        likesNight=False,
        dislikesWeekend=False,
        history=UserHistory(
            weekdayCount=0, weekendCount=0, expectedTotal=0,
            slotTypeCounts=SlotTypeCounts(A=0, B=0, C=0, D=0, E=0, F=0)
        )
    )


def create_weekday_slots(slot_date: date, a_count: int = 4, b_count: int = 2, c_count: int = 2) -> list[Slot]:
    """Hafta içi günü için A, B, C slotları"""
    slots = []
    date_str = slot_date.isoformat()
    
    # A slotu
    a_seats = [Seat(id=f"A_{date_str}_s{i}", role=None) for i in range(a_count)]
    slots.append(Slot(id=f"A_{date_str}", date=slot_date, dutyType="A", dayType=DayType.WEEKDAY, seats=a_seats))
    
    # B slotu
    b_seats = [Seat(id=f"B_{date_str}_s{i}", role=None) for i in range(b_count)]
    slots.append(Slot(id=f"B_{date_str}", date=slot_date, dutyType="B", dayType=DayType.WEEKDAY, seats=b_seats))
    
    # C slotu
    c_seats = [Seat(id=f"C_{date_str}_s{i}", role=None) for i in range(c_count)]
    slots.append(Slot(id=f"C_{date_str}", date=slot_date, dutyType="C", dayType=DayType.WEEKDAY, seats=c_seats))
    
    return slots


def create_weekend_slots(slot_date: date, d_count: int = 2, e_count: int = 2, f_count: int = 1) -> list[Slot]:
    """Hafta sonu günü için D, E, F slotları"""
    slots = []
    date_str = slot_date.isoformat()
    
    # D slotu
    d_seats = [Seat(id=f"D_{date_str}_s{i}", role=None) for i in range(d_count)]
    slots.append(Slot(id=f"D_{date_str}", date=slot_date, dutyType="D", dayType=DayType.WEEKEND, seats=d_seats))
    
    # E slotu
    e_seats = [Seat(id=f"E_{date_str}_s{i}", role=None) for i in range(e_count)]
    slots.append(Slot(id=f"E_{date_str}", date=slot_date, dutyType="E", dayType=DayType.WEEKEND, seats=e_seats))
    
    # F slotu
    f_seats = [Seat(id=f"F_{date_str}_s{i}", role=None) for i in range(f_count)]
    slots.append(Slot(id=f"F_{date_str}", date=slot_date, dutyType="F", dayType=DayType.WEEKEND, seats=f_seats))
    
    return slots


def main():
    print("="*80)
    print("ADALET TESTİ - HIÇ UNAVAILABILITY YOK")
    print("="*80)
    
    solver = SchedulerSolver()
    
    # 26 kullanıcı (gerçekçi senaryo)
    users = [create_user(f"u{i:02d}", f"User {i+1}") for i in range(26)]
    
    # 4 hafta (28 gün)
    start = date(2025, 12, 15)
    slots = []
    
    for day_offset in range(28):
        d = start + timedelta(days=day_offset)
        weekday = d.weekday()
        
        if weekday < 5:  # Hafta içi
            slots.extend(create_weekday_slots(d))
        else:  # Hafta sonu
            slots.extend(create_weekend_slots(d))
    
    period = Period(id="test", name="Test", startDate=start, endDate=start + timedelta(days=27))
    
    # HİÇ UNAVAILABILITY YOK
    request = ScheduleRequest(period=period, users=users, slots=slots, unavailability=[])
    
    # Toplam koltuk sayısı
    total_seats = sum(len(s.seats) for s in slots)
    ideal_per_user = total_seats / len(users)
    
    print(f"\nSENARYO:")
    print(f"  Kullanıcı sayısı: {len(users)}")
    print(f"  Toplam gün: 28")
    print(f"  Toplam koltuk: {total_seats}")
    print(f"  Kişi başı ideal: {ideal_per_user:.2f}")
    print(f"  Unavailability: YOK")
    
    print("\nÇözülüyor...")
    response = solver.solve(request)
    
    print(f"\n{'='*80}")
    print("SONUÇLAR")
    print(f"{'='*80}")
    print(f"Status: {response.meta.solverStatus}")
    print(f"Base: {response.meta.base}")
    print(f"Min/Max: {response.meta.minShifts}/{response.meta.maxShifts}")
    print(f"Fark: {response.meta.maxShifts - response.meta.minShifts}")
    
    # Kullanıcı bazında analiz
    user_stats = defaultdict(lambda: {"total": 0, "A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0, "weekend": 0})
    
    for a in response.assignments:
        user_stats[a.userId]["total"] += 1
        slot_id = a.slotId
        duty_type = slot_id.split("_")[0]  # A, B, C, D, E, F
        user_stats[a.userId][duty_type] += 1
        if duty_type in ("D", "E", "F"):
            user_stats[a.userId]["weekend"] += 1
    
    print(f"\n{'='*80}")
    print("KULLANICI DAĞILIMI")
    print(f"{'='*80}")
    print(f"{'User':<10} {'Total':<8} {'A':<5} {'B':<5} {'C':<5} {'D':<5} {'E':<5} {'F':<5} {'Weekend':<8}")
    print("-"*80)
    
    totals = []
    a_counts = []
    weekend_counts = []
    
    for uid in sorted(user_stats.keys()):
        stats = user_stats[uid]
        print(f"{uid:<10} {stats['total']:<8} {stats['A']:<5} {stats['B']:<5} {stats['C']:<5} {stats['D']:<5} {stats['E']:<5} {stats['F']:<5} {stats['weekend']:<8}")
        totals.append(stats['total'])
        a_counts.append(stats['A'])
        weekend_counts.append(stats['weekend'])
    
    print(f"\n{'='*80}")
    print("ANALİZ")
    print(f"{'='*80}")
    
    # Toplam nöbet
    total_diff = max(totals) - min(totals)
    print(f"  Toplam nöbet farkı: {total_diff} (max={max(totals)}, min={min(totals)})")
    if total_diff > 2:
        print(f"  ❌ HATA! Fark 2'den büyük olmamalı!")
    else:
        print(f"  ✅ Toplam dağılım kabul edilebilir (±2)")
    
    # A nöbeti
    a_diff = max(a_counts) - min(a_counts)
    print(f"\n  A nöbeti farkı: {a_diff} (max={max(a_counts)}, min={min(a_counts)})")
    if a_diff > 2:
        print(f"  ❌ UYARI! A nöbetleri dengesiz")
    
    # Weekend
    weekend_diff = max(weekend_counts) - min(weekend_counts)
    print(f"\n  Weekend farkı: {weekend_diff} (max={max(weekend_counts)}, min={min(weekend_counts)})")
    if weekend_diff > 2:
        print(f"  ❌ UYARI! Weekend nöbetleri dengesiz")
    
    return total_diff <= 2


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

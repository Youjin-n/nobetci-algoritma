"""
Test to debug C→A forbidden transition bug.

Bu test, C nöbetinden sonra ertesi gün A nöbeti atanıp atanmadığını kontrol eder.
"""
import json
from datetime import date, timedelta

from app.services.scheduler.solver import SchedulerSolver
from app.schemas.schedule import (
    ScheduleRequest, User, Slot, Unavailability, Period, UserHistory, Seat, SlotTypeCounts, DayType
)


def create_user(user_id: str, name: str) -> User:
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


def create_slot(slot_id: str, slot_date: date, duty_type: str, seat_count: int) -> Slot:
    day_type = DayType.WEEKEND if duty_type in ("D", "E", "F") else DayType.WEEKDAY
    seats = [Seat(id=f"{slot_id}_s{i}", role=None) for i in range(seat_count)]
    return Slot(id=slot_id, date=slot_date, dutyType=duty_type, dayType=day_type, seats=seats)


def main():
    print("="*70)
    print("C→A YASAK GEÇİŞ TESTİ")
    print("="*70)
    
    solver = SchedulerSolver()
    period = Period(id="test", name="Test", startDate=date(2025, 12, 15), endDate=date(2025, 12, 17))
    
    # 3 kullanıcı - az sayıda olunca constraint'in çalışıp çalışmadığını görmek kolay
    users = [
        create_user("u1", "Ahmet"),
        create_user("u2", "Mehmet"),
        create_user("u3", "Ayşe"),
    ]
    
    # 15 Aralık: A, B, C
    # 16 Aralık: A, B, C
    # Eğer constraint çalışıyorsa, 15'te C alan kişi 16'da A almamalı
    slots = [
        # Gün 1: 15 Aralık
        create_slot("A_15", date(2025, 12, 15), "A", 1),
        create_slot("B_15", date(2025, 12, 15), "B", 1),
        create_slot("C_15", date(2025, 12, 15), "C", 1),
        # Gün 2: 16 Aralık
        create_slot("A_16", date(2025, 12, 16), "A", 1),
        create_slot("B_16", date(2025, 12, 16), "B", 1),
        create_slot("C_16", date(2025, 12, 16), "C", 1),
    ]
    
    request = ScheduleRequest(period=period, users=users, slots=slots, unavailability=[])
    
    print("\nSENARYO:")
    print("  3 kullanıcı, 2 gün")
    print("  Her gün: A (1 kişi), B (1 kişi), C (1 kişi)")
    print("  Base = 6 slot / 3 kişi = 2")
    print("\nBEKLENTİ:")
    print("  AYNI GÜN C ve A aynı kişiye atanamaz!")
    print("  (C sabah 08:30'da biter, A sabah 08:30'da başlar)")
    
    response = solver.solve(request)
    
    print(f"\n{'='*70}")
    print("SONUÇ")
    print(f"{'='*70}")
    print(f"Status: {response.meta.solverStatus}")
    
    # Atama detayları
    user_slots = {u.id: [] for u in users}
    slot_users = {}
    
    for a in response.assignments:
        user_slots[a.userId].append(a.slotId)
        slot_users[a.slotId] = a.userId
    
    print(f"\nATAMALAR:")
    for uid, slots_list in user_slots.items():
        print(f"  {uid}: {sorted(slots_list)}")
    
    print(f"\nSLOT BAZINDA:")
    for slot in ["A_15", "B_15", "C_15", "A_16", "B_16", "C_16"]:
        print(f"  {slot}: {slot_users.get(slot, 'BOŞ')}")
    
    # Yasak geçiş kontrolü - AYNI GÜN
    c_15_user = slot_users.get("C_15")
    a_15_user = slot_users.get("A_15")
    c_16_user = slot_users.get("C_16")
    a_16_user = slot_users.get("A_16")
    
    print(f"\n{'='*70}")
    print("YASAK GEÇİŞ ANALİZİ (AYNI GÜN)")
    print(f"{'='*70}")
    
    violations = []
    
    # 15 Aralık: C ve A aynı kişiye atanamaz
    print(f"  15 Aralık C: {c_15_user}")
    print(f"  15 Aralık A: {a_15_user}")
    if c_15_user == a_15_user:
        print(f"  ❌ HATA! {c_15_user} hem 15'te C hem 15'te A almış!")
        violations.append("15 Aralık")
    else:
        print(f"  ✅ Doğru!")
    
    # 16 Aralık: C ve A aynı kişiye atanamaz  
    print(f"\n  16 Aralık C: {c_16_user}")
    print(f"  16 Aralık A: {a_16_user}")
    if c_16_user == a_16_user:
        print(f"  ❌ HATA! {c_16_user} hem 16'da C hem 16'da A almış!")
        violations.append("16 Aralık")
    else:
        print(f"  ✅ Doğru!")
    
    if violations:
        print(f"\n❌ TOPLAM {len(violations)} İHLAL!")
        return False
    else:
        print(f"\n✅ Tüm yasak geçişler doğru engellendi!")
        return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

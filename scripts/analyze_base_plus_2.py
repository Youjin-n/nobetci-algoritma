"""
BASE+2 ZORLAMALI - ÇOK DARBOĞAZLI SENARYO

Bu test, +2/-2 durumlarını KESIN oluşturacak darboğazlar yaratır.

SENARYO: 6 kişi, 10 gün
- Her gün A (2), B (1), C (1) = 4 kişi/gün
- 10 gün × 4 = 40 koltuk / 6 kişi = base ~6-7

ÇOKlu DARBOĞAZ:
1. u0, u1, u2, u3, u4 (5 kişi) tüm gece nöbetlerini (C) kapatmış
   → Sadece u5 geceye yazılabilir = 10 gece, 1 kişi!
   
2. u0, u1, u2 Pazartesi kapalı (3 kişi)
   → Pazartesi için sadece u3, u4, u5 müsait
   
3. u3, u4 Cuma kapalı (2 kişi) 
   → Cuma için sadece u0, u1, u2, u5 müsait
   
Sonuç: u5 hem tüm geceleri almak zorunda + üstüne pazartesi de girmesi lazım
       Bu durumda u5 kesinlikle base+2 veya daha fazla olacak!
"""

import json
from datetime import date, timedelta
from pathlib import Path

from app.services.scheduler.solver import SchedulerSolver
from app.schemas.schedule import (
    ScheduleRequest, User, Slot, Unavailability, Period, UserHistory, Seat, SlotTypeCounts, DayType
)

OUTPUT_DIR = Path("test_outputs")


def create_user(user_id: str, name: str) -> User:
    return User(
        id=user_id,
        name=name,
        likesNight=False,
        dislikesWeekend=False,
        history=UserHistory(weekdayCount=0, weekendCount=0, expectedTotal=0,
                           slotTypeCounts=SlotTypeCounts(A=0, B=0, C=0, D=0, E=0, F=0))
    )


def create_slot(slot_id: str, slot_date: date, duty_type: str, seat_count: int) -> Slot:
    day_type = DayType.WEEKDAY
    seats = [Seat(id=f"{slot_id}_s{i}", role=None) for i in range(seat_count)]
    return Slot(id=slot_id, date=slot_date, dutyType=duty_type, dayType=day_type, seats=seats)


def main():
    print("="*70)
    print("BASE+2 ZORLAMALI - ÇOK DARBOĞAZLI SENARYO")
    print("="*70)
    
    solver = SchedulerSolver()
    period = Period(id="test", name="Test", startDate=date(2025, 12, 1), endDate=date(2025, 12, 12))
    
    # 6 kullanıcı
    users = [create_user(f"u{i}", f"Asistan {i}") for i in range(6)]
    
    slots = []
    unavailability = []
    start = date(2025, 12, 1)  # Pazartesi
    
    night_slots = []
    monday_slots = []
    friday_slots = []
    
    for day_offset in range(10):  # 10 gün (2 hafta, hafta içi)
        d = start + timedelta(days=day_offset)
        
        # Hafta sonlarını atla
        if d.weekday() >= 5:
            continue
            
        slots.append(create_slot(f"A_{d}", d, "A", 2))
        slots.append(create_slot(f"B_{d}", d, "B", 1))
        slots.append(create_slot(f"C_{d}", d, "C", 1))
        night_slots.append(f"C_{d}")
        
        if d.weekday() == 0:  # Pazartesi
            monday_slots.extend([f"A_{d}", f"B_{d}", f"C_{d}"])
        if d.weekday() == 4:  # Cuma
            friday_slots.extend([f"A_{d}", f"B_{d}", f"C_{d}"])
    
    total_seats = sum(len(s.seats) for s in slots)
    base = total_seats // len(users)
    
    print(f"\nSENARYO:")
    print(f"  - 6 kullanıcı")
    print(f"  - {len(slots)} slot, {total_seats} koltuk")
    print(f"  - Base = {base}")
    print(f"  - Gece slotu: {len(night_slots)}")
    print(f"  - Pazartesi slotu: {len(monday_slots)}")
    print(f"  - Cuma slotu: {len(friday_slots)}")
    
    # DARBOĞAZ 1: u0-u4 (5 kişi) TÜM geceleri kapatmış
    print(f"\nDARBOĞAZ 1: Gece nöbetleri")
    print(f"  u0, u1, u2, u3, u4 (5 kişi) -> TÜM geceler kapalı")
    print(f"  Sadece u5 geceye yazılabilir!")
    print(f"  {len(night_slots)} gece / 1 kişi = u5 en az {len(night_slots)} gece alacak!")
    for i in range(5):
        for night_slot in night_slots:
            unavailability.append(Unavailability(userId=f"u{i}", slotId=night_slot))
    
    # DARBOĞAZ 2: u0, u1, u2 Pazartesi kapalı
    print(f"\nDARBOĞAZ 2: Pazartesi")
    print(f"  u0, u1, u2 (3 kişi) -> Pazartesi kapalı")
    print(f"  Sadece u3, u4, u5 pazartesiye yazılabilir")
    for i in range(3):
        for mon_slot in monday_slots:
            if "C_" not in mon_slot:  # Gece zaten yukarıda kapatıldı
                unavailability.append(Unavailability(userId=f"u{i}", slotId=mon_slot))
    
    # DARBOĞAZ 3: u3, u4 Cuma kapalı
    print(f"\nDARBOĞAZ 3: Cuma")
    print(f"  u3, u4 (2 kişi) -> Cuma kapalı")
    print(f"  Sadece u0, u1, u2, u5 cumaya yazılabilir")
    for i in range(3, 5):
        for fri_slot in friday_slots:
            if "C_" not in fri_slot:  # Gece zaten yukarıda kapatıldı
                unavailability.append(Unavailability(userId=f"u{i}", slotId=fri_slot))
    
    print(f"\nÖZET:")
    print(f"  u5 -> Sadece gece yazılabilir kişi + hem Pazartesi hem Cuma müsait")
    print(f"  u5'in minimum yükü: {len(night_slots)} gece nöbeti")
    print(f"  Base = {base}, yani u5 kesinlikle base+{len(night_slots)-base} olacak!")
    
    request = ScheduleRequest(period=period, users=users, slots=slots, unavailability=unavailability)
    
    print(f"\nÇözülüyor...")
    response = solver.solve(request)
    
    print(f"\n{'='*70}")
    print(f"SONUÇ")
    print(f"{'='*70}")
    print(f"Status: {response.meta.solverStatus}")
    print(f"Base: {response.meta.base}")
    print(f"Min: {response.meta.minShifts}, Max: {response.meta.maxShifts}")
    print(f"Unavailability Violations: {response.meta.unavailabilityViolations}")
    print(f"Users at Base+2: {response.meta.usersAtBasePlus2}")
    
    # Detaylı analiz
    user_data = {f"u{i}": {"total": 0, "night": 0, "monday": 0, "friday": 0} for i in range(6)}
    
    for a in response.assignments:
        user_data[a.userId]["total"] += 1
        if "C_" in a.slotId:
            user_data[a.userId]["night"] += 1
        if any(mon in a.slotId for mon in ["2025-12-01", "2025-12-08"]):  # Pazartesiler
            user_data[a.userId]["monday"] += 1
        if any(fri in a.slotId for fri in ["2025-12-05", "2025-12-12"]):  # Cumalar
            user_data[a.userId]["friday"] += 1
    
    print(f"\nDETAYLI DAĞILIM:")
    print("-"*70)
    print(f"{'Kullanıcı':<10} {'Toplam':<8} {'Gece':<6} {'Pzt':<6} {'Cuma':<6} {'Durum'}")
    print("-"*70)
    
    for uid in sorted(user_data.keys()):
        d = user_data[uid]
        diff = d["total"] - base
        
        if diff >= 2:
            status = f"⚠️  BASE+{diff}!"
        elif diff == 1:
            status = f"base+1"
        elif diff <= -2:
            status = f"⚠️  BASE{diff}!"
        elif diff == -1:
            status = f"base-1"
        else:
            status = "base"
        
        print(f"{uid:<10} {d['total']:<8} {d['night']:<6} {d['monday']:<6} {d['friday']:<6} {status}")
    
    # Gece detayı
    print(f"\nGECE NÖBETİ DETAYI:")
    for night_slot in night_slots:
        for a in response.assignments:
            if a.slotId == night_slot:
                closed = a.userId in [f"u{i}" for i in range(5)]
                marker = " ❌ VİOLATION" if closed else ""
                print(f"  {night_slot} -> {a.userId}{marker}")
    
    if response.meta.warnings:
        print(f"\nWARNINGS: {response.meta.warnings}")
    
    # Sonuç açıklaması
    print(f"\n{'='*70}")
    print(f"SONUÇ AÇIKLAMASI")
    print(f"{'='*70}")
    
    u5_total = user_data["u5"]["total"]
    u5_night = user_data["u5"]["night"]
    
    if u5_total >= base + 2:
        print(f"✅ BASE+2 DURUMU GERÇEKLEŞTİ!")
        print(f"   u5: {u5_total} nöbet (base {base} + {u5_total - base})")
        print(f"   Sebep: u5 tek geceye müsait kişiydi, {u5_night} gece aldı")
    else:
        print(f"Base+2 durumu gerçekleşmedi.")
        print(f"   u5: {u5_total} nöbet")
    
    if response.meta.unavailabilityViolations > 0:
        print(f"\n⚠️  {response.meta.unavailabilityViolations} unavailability violation var!")
        print(f"   Base+2 hard limit olduğu için bazı kapalı slotlara atama yapıldı.")
    
    # JSON kaydet
    output = {
        "scenario": "Base+2 Zorlamalı - Çok Darboğazlı",
        "bottlenecks": {
            "night": {"closed_by": ["u0", "u1", "u2", "u3", "u4"], "only_available": ["u5"]},
            "monday": {"closed_by": ["u0", "u1", "u2"], "available": ["u3", "u4", "u5"]},
            "friday": {"closed_by": ["u3", "u4"], "available": ["u0", "u1", "u2", "u5"]}
        },
        "parameters": {
            "users": 6,
            "total_seats": total_seats,
            "base": base,
            "night_slots": len(night_slots)
        },
        "result": {
            "status": response.meta.solverStatus,
            "base": response.meta.base,
            "min": response.meta.minShifts,
            "max": response.meta.maxShifts,
            "violations": response.meta.unavailabilityViolations,
            "at_base_plus_2": response.meta.usersAtBasePlus2
        },
        "distribution": {uid: d["total"] for uid, d in user_data.items()},
        "night_distribution": {uid: d["night"] for uid, d in user_data.items()},
        "conclusion": f"u5 toplam {u5_total} nöbet aldı (base+{u5_total-base})"
    }
    
    with open(OUTPUT_DIR / "base_plus_2_multi_bottleneck.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\nSonuç: {OUTPUT_DIR / 'base_plus_2_multi_bottleneck.json'}")


if __name__ == "__main__":
    main()

"""
Kümelenmiş Unavailability Testi

26 kişi, 28 gün, %60-80 arası unavailability
AMA: Herkes benzer slotları kapatıyor (Çarşamba, hafta sonu, gece vs.)

Bu test algoritmayı zorlar çünkü:
- Rastgele değil, kümelenmiş kapatmalar
- Bazı slotlara neredeyse kimse müsait değil
"""
import random
from collections import defaultdict
from datetime import date, timedelta

from app.schemas.schedule import (
    DayType, DutyType, Period, ScheduleRequest, Seat, Slot,
    SlotTypeCounts, Unavailability, User, UserHistory,
)
from app.services.scheduler import SchedulerSolver


def create_clustered_unavailability(users, slots, seed=42):
    """
    Kümelenmiş unavailability oluştur.
    
    Senaryolar:
    1. Çarşamba günleri çok popüler kapatma günü (%90 kapatır)
    2. Cuma akşamları (B, C) çok kapatılır (%85)
    3. Hafta sonu sabahları (D) kapatılır (%80)
    4. Gece nöbetleri (C, F) genel olarak kapatılır (%70)
    5. Diğer slotlar normal (%40-60)
    """
    random.seed(seed)
    unavailability = []
    
    slot_info = {}
    for s in slots:
        day_name = s.slot_date.strftime("%A")
        slot_info[s.id] = {
            "date": s.slot_date,
            "day_name": day_name,
            "duty_type": s.dutyType.value,
            "is_weekend": s.dayType == DayType.WEEKEND,
        }
    
    for user in users:
        # Her kullanıcı için base unavailability oranı (%60-80 arası)
        base_rate = random.uniform(0.60, 0.80)
        
        for slot in slots:
            info = slot_info[slot.id]
            
            # Slot'a göre kapatma olasılığını belirle
            close_prob = base_rate * 0.5  # Base: %30-40
            
            # 1. ÇARŞAMBA: Çok popüler kapatma
            if info["day_name"] == "Wednesday":
                close_prob = min(0.95, base_rate + 0.25)
            
            # 2. CUMA AKŞAM/GECE (B, C)
            elif info["day_name"] == "Friday" and info["duty_type"] in ("B", "C"):
                close_prob = min(0.90, base_rate + 0.20)
            
            # 3. HAFTA SONU SABAH (D)
            elif info["is_weekend"] and info["duty_type"] == "D":
                close_prob = min(0.85, base_rate + 0.15)
            
            # 4. GECE NÖBETLERİ (C, F)
            elif info["duty_type"] in ("C", "F"):
                close_prob = min(0.80, base_rate + 0.10)
            
            # 5. PAZARTESİ SABAH (A) - Herkes kaçar
            elif info["day_name"] == "Monday" and info["duty_type"] == "A":
                close_prob = min(0.88, base_rate + 0.18)
            
            if random.random() < close_prob:
                unavailability.append(Unavailability(userId=user.id, slotId=slot.id))
    
    return unavailability


def analyze_slot_availability(users, slots, unavailability):
    """Slot bazında müsaitlik analizi"""
    unavail_set = {(u.userId, u.slotId) for u in unavailability}
    
    stats = []
    for slot in slots:
        avail = sum(1 for u in users if (u.id, slot.id) not in unavail_set)
        req = len(slot.seats)
        day_name = slot.slot_date.strftime("%a")
        stats.append({
            "id": slot.id,
            "day": day_name,
            "date": slot.slot_date,
            "type": slot.dutyType.value,
            "avail": avail,
            "req": req,
            "ratio": avail / req if req > 0 else 0,
            "critical": avail <= req,
            "impossible": avail < req,
        })
    
    return stats


def run_test():
    random.seed(42)
    
    # 26 kullanıcı
    users = [
        User(
            id=f"user_{i+1:02d}",
            name=f"Kullanıcı {i+1}",
            email=f"user{i+1}@test.com",
            history=UserHistory(
                weekdayCount=0, weekendCount=0, expectedTotal=0,
                slotTypeCounts=SlotTypeCounts(A=0, B=0, C=0, D=0, E=0, F=0),
            ),
            likesNight=False,
            dislikesWeekend=False,
        )
        for i in range(26)
    ]
    
    # 28 günlük slotlar
    slots = []
    slot_id = 1
    start_date = date(2025, 12, 1)
    
    weekday_config = {DutyType.A: 3, DutyType.B: 2, DutyType.C: 2}
    weekend_config = {DutyType.D: 2, DutyType.E: 2, DutyType.F: 2}
    
    for day in range(28):
        current_date = start_date + timedelta(days=day)
        is_weekend = current_date.weekday() >= 5
        day_type = DayType.WEEKEND if is_weekend else DayType.WEEKDAY
        config = weekend_config if is_weekend else weekday_config
        
        for duty_type, count in config.items():
            seats = [Seat(id=f"slot{slot_id}_s{j}", role=None) for j in range(count)]
            slots.append(Slot(
                id=f"slot_{slot_id}",
                date=current_date,
                dutyType=duty_type,
                dayType=day_type,
                seats=seats,
            ))
            slot_id += 1
    
    # Kümelenmiş unavailability
    unavailability = create_clustered_unavailability(users, slots)
    
    # Analiz
    stats = analyze_slot_availability(users, slots, unavailability)
    
    total_slots = len(slots)
    total_seats = sum(len(s.seats) for s in slots)
    avg_unavail = len(unavailability) / (len(users) * total_slots) * 100
    
    critical_slots = [s for s in stats if s["critical"]]
    impossible_slots = [s for s in stats if s["impossible"]]
    
    print("=" * 70)
    print("  KÜMELENMİŞ UNAVAILABILITY TESTİ")
    print("  (Herkes benzer slotları kapatıyor)")
    print("=" * 70)
    
    print(f"\n📊 GİRİŞ VERİLERİ:")
    print(f"   Kullanıcı: {len(users)}")
    print(f"   Slot: {total_slots}, Koltuk: {total_seats}")
    print(f"   Ortalama unavailability: %{avg_unavail:.1f}")
    print(f"   Base: {total_seats // len(users)}")
    
    print(f"\n⚠️  KRİTİK SLOTLAR:")
    print(f"   Kritik (müsait <= gerekli): {len(critical_slots)}")
    print(f"   İmkansız (müsait < gerekli): {len(impossible_slots)}")
    
    if critical_slots:
        print(f"\n   En zor 10 slot:")
        sorted_slots = sorted(stats, key=lambda x: x["ratio"])[:10]
        for s in sorted_slots:
            print(f"   {s['day']} {s['date']} {s['type']}: {s['avail']} müsait / {s['req']} gerekli")
    
    # Çöz
    print(f"\n🔄 Çözülüyor...")
    solver = SchedulerSolver()
    period = Period(
        id="test", name="Test",
        startDate=start_date, endDate=start_date + timedelta(days=27)
    )
    request = ScheduleRequest(
        period=period, users=users, slots=slots, unavailability=unavailability
    )
    
    response = solver.solve(request)
    
    # Sonuç analizi
    unavail_set = {(u.userId, u.slotId) for u in unavailability}
    violations = []
    user_counts = defaultdict(int)
    user_violations = defaultdict(int)
    
    for a in response.assignments:
        user_counts[a.userId] += 1
        if (a.userId, a.slotId) in unavail_set:
            violations.append((a.userId, a.slotId))
            user_violations[a.userId] += 1
    
    total_assignments = len(response.assignments)
    success_rate = (total_assignments - len(violations)) / total_assignments * 100
    counts = list(user_counts.values())
    
    # Zorunlu vs opsiyonel
    forced = sum(1 for uid, sid in violations 
                 for s in stats if s["id"] == sid and s["avail"] <= s["req"])
    
    print(f"\n📈 SONUÇLAR:")
    print(f"   Solver: {response.meta.solverStatus}")
    print(f"   Süre: {response.meta.solveTimeMs:.0f} ms")
    print(f"   Toplam atama: {total_assignments}")
    
    print(f"\n🎯 BAŞARI ORANI:")
    print(f"   Violation: {len(violations)} / {total_assignments}")
    print(f"   SUCCESS RATE: %{success_rate:.1f}")
    print(f"   Zorunlu violation: {forced}")
    print(f"   Opsiyonel violation: {len(violations) - forced}")
    
    print(f"\n⚖️  DAĞILIM:")
    print(f"   Min: {min(counts)}, Max: {max(counts)}, Fark: {max(counts) - min(counts)}")
    print(f"   Base: {response.meta.base}")
    
    # Violation dağılımı
    if user_violations:
        max_viol = max(user_violations.values())
        viol_dist = defaultdict(int)
        for v in user_violations.values():
            viol_dist[v] += 1
        print(f"\n📊 Violation Dağılımı (kişi başı):")
        for v in sorted(viol_dist.keys()):
            print(f"   {v} violation: {viol_dist[v]} kişi")
    
    print("=" * 70)


if __name__ == "__main__":
    run_test()

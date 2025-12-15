"""
Detaylı fairness testi - tüm sonuçları dosyaya yazar.
Hiç unavailability yok, herkes eşit - TAM ADİL DAĞILIM BEKLİYORUZ.
"""
import json
from datetime import date, timedelta
from collections import defaultdict, Counter

from app.services.scheduler.solver import SchedulerSolver
from app.schemas.schedule import *


def main():
    # 26 kullanıcı - hepsi yeni, hiç history yok
    users = [User(
        id=f'u{i:02d}',
        name=f'User {i+1}',
        likesNight=False,
        dislikesWeekend=False,
        history=UserHistory(
            weekdayCount=0,
            weekendCount=0,
            expectedTotal=0,
            slotTypeCounts=SlotTypeCounts(A=0, B=0, C=0, D=0, E=0, F=0)
        )
    ) for i in range(26)]

    # 42 gün - gerçek senaryo
    slots = []
    start = date(2025, 12, 15)
    
    weekday_count = 0
    weekend_count = 0
    
    for d_off in range(42):
        d = start + timedelta(days=d_off)
        ds = d.isoformat()
        
        if d.weekday() < 5:  # Hafta içi
            weekday_count += 1
            # A: 3 koltuk, B: 2, C: 2
            slots.append(Slot(id=f'A_{ds}', date=d, dutyType='A', dayType=DayType.WEEKDAY,
                             seats=[Seat(id=f'A_{ds}_s{i}', role=None) for i in range(3)]))
            slots.append(Slot(id=f'B_{ds}', date=d, dutyType='B', dayType=DayType.WEEKDAY,
                             seats=[Seat(id=f'B_{ds}_s{i}', role=None) for i in range(2)]))
            slots.append(Slot(id=f'C_{ds}', date=d, dutyType='C', dayType=DayType.WEEKDAY,
                             seats=[Seat(id=f'C_{ds}_s{i}', role=None) for i in range(2)]))
        else:  # Hafta sonu
            weekend_count += 1
            # D, E, F: 2 koltuk
            slots.append(Slot(id=f'D_{ds}', date=d, dutyType='D', dayType=DayType.WEEKEND,
                             seats=[Seat(id=f'D_{ds}_s{i}', role=None) for i in range(2)]))
            slots.append(Slot(id=f'E_{ds}', date=d, dutyType='E', dayType=DayType.WEEKEND,
                             seats=[Seat(id=f'E_{ds}_s{i}', role=None) for i in range(2)]))
            slots.append(Slot(id=f'F_{ds}', date=d, dutyType='F', dayType=DayType.WEEKEND,
                             seats=[Seat(id=f'F_{ds}_s{i}', role=None) for i in range(2)]))

    period = Period(id='test', name='Test', startDate=start, endDate=start + timedelta(days=41))
    req = ScheduleRequest(period=period, users=users, slots=slots, unavailability=[])  # HİÇ unavailability YOK!

    # Hesaplamalar
    total_a = weekday_count * 3
    total_b = weekday_count * 2
    total_c = weekday_count * 2
    total_weekend = weekend_count * 6  # D+E+F = 2+2+2 = 6 per day
    total_seats = total_a + total_b + total_c + total_weekend

    print("=" * 80)
    print("DETAYLI FAİRNESS TESTİ")
    print("=" * 80)
    print(f"\nKONFİGÜRASYON:")
    print(f"  Kullanıcı: 26 (hepsi yeni, history=0)")
    print(f"  Dönem: 42 gün ({weekday_count} hafta içi, {weekend_count} hafta sonu)")
    print(f"  Unavailability: HİÇ YOK!")
    print(f"\nKOLTUK SAYILARI:")
    print(f"  A toplam: {total_a} ({total_a/26:.1f} kişi başı ideal)")
    print(f"  B toplam: {total_b} ({total_b/26:.1f} kişi başı ideal)")
    print(f"  C toplam: {total_c} ({total_c/26:.1f} kişi başı ideal)")
    print(f"  Weekend toplam: {total_weekend} ({total_weekend/26:.1f} kişi başı ideal)")
    print(f"  TOPLAM: {total_seats} ({total_seats/26:.1f} kişi başı ideal)")

    print("\nÇözülüyor...")
    solver = SchedulerSolver()
    resp = solver.solve(req)

    # Detaylı analiz
    user_stats = defaultdict(lambda: {'total': 0, 'A': 0, 'B': 0, 'C': 0, 'D': 0, 'E': 0, 'F': 0})
    
    for assignment in resp.assignments:
        uid = assignment.userId
        slot_id = assignment.slotId
        duty_type = slot_id.split('_')[0]
        user_stats[uid]['total'] += 1
        user_stats[uid][duty_type] += 1

    print("\n" + "=" * 80)
    print("SONUÇLAR")
    print("=" * 80)
    print(f"\nMeta: Status={resp.meta.solverStatus}, Min={resp.meta.minShifts}, Max={resp.meta.maxShifts}")
    print(f"Fark: {resp.meta.maxShifts - resp.meta.minShifts}")

    # Kullanıcı tablosu
    print(f"\n{'User':<8} {'Total':<6} {'A':<4} {'B':<4} {'C':<4} {'D':<4} {'E':<4} {'F':<4} {'Weekend':<8}")
    print("-" * 60)
    
    for uid in sorted(user_stats.keys()):
        s = user_stats[uid]
        weekend = s['D'] + s['E'] + s['F']
        print(f"{uid:<8} {s['total']:<6} {s['A']:<4} {s['B']:<4} {s['C']:<4} {s['D']:<4} {s['E']:<4} {s['F']:<4} {weekend:<8}")

    # Özet istatistikler
    print("\n" + "=" * 80)
    print("ÖZET İSTATİSTİKLER")
    print("=" * 80)
    
    totals = [s['total'] for s in user_stats.values()]
    a_counts = [s['A'] for s in user_stats.values()]
    b_counts = [s['B'] for s in user_stats.values()]
    c_counts = [s['C'] for s in user_stats.values()]
    weekend_counts = [s['D'] + s['E'] + s['F'] for s in user_stats.values()]

    print(f"\nTOPLAM: min={min(totals)}, max={max(totals)}, fark={max(totals)-min(totals)}")
    print(f"  Dağılım: {dict(sorted(Counter(totals).items()))}")
    
    print(f"\nA NÖBETİ: min={min(a_counts)}, max={max(a_counts)}, fark={max(a_counts)-min(a_counts)}")
    print(f"  Dağılım: {dict(sorted(Counter(a_counts).items()))}")
    
    print(f"\nB NÖBETİ: min={min(b_counts)}, max={max(b_counts)}, fark={max(b_counts)-min(b_counts)}")
    print(f"  Dağılım: {dict(sorted(Counter(b_counts).items()))}")
    
    print(f"\nC NÖBETİ: min={min(c_counts)}, max={max(c_counts)}, fark={max(c_counts)-min(c_counts)}")
    print(f"  Dağılım: {dict(sorted(Counter(c_counts).items()))}")
    
    print(f"\nWEEKEND: min={min(weekend_counts)}, max={max(weekend_counts)}, fark={max(weekend_counts)-min(weekend_counts)}")
    print(f"  Dağılım: {dict(sorted(Counter(weekend_counts).items()))}")

    # Değerlendirme
    print("\n" + "=" * 80)
    print("DEĞERLENDİRME")
    print("=" * 80)
    
    issues = []
    if max(totals) - min(totals) > 2:
        issues.append(f"❌ Toplam fark {max(totals)-min(totals)} > 2")
    if max(a_counts) - min(a_counts) > 2:
        issues.append(f"❌ A fark {max(a_counts)-min(a_counts)} > 2")
    if max(weekend_counts) - min(weekend_counts) > 2:
        issues.append(f"❌ Weekend fark {max(weekend_counts)-min(weekend_counts)} > 2")
    
    if issues:
        print("\n❌ SORUNLAR:")
        for issue in issues:
            print(f"   {issue}")
    else:
        print("\n✅ TÜM DAĞILIMLAR ADİL (fark ≤ 2)")


if __name__ == "__main__":
    main()

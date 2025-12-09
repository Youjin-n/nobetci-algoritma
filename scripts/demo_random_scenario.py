"""Demo: 20 eski + 25 yeni AÖ için rastgele senaryo.
- 28 gün (1-28 Aralık 2025)
- Hafta içi: A(3), B(2), C(2)
- Hafta sonu: D(2), E(2), F(2)
- Rastgele müsaitlik (eski: %12, yeni: %18)
- Tarihsel nöbetler (eski için rastgele)
Çıktı: Her kullanıcı için toplam ve A/B/C/D/E/F dağılımı.
"""

import random
from datetime import date, timedelta
from collections import defaultdict

from app.schemas.schedule import (
    ScheduleRequest,
    User,
    UserHistory,
    UserPreferences,
    Slot,
    Unavailability,
    Period,
    DutyType,
    DayType,
)
from app.services.scheduler import SchedulerSolver

random.seed(1234)

NAMES = [
    "Ahmet", "Mehmet", "Ayse", "Fatma", "Ali", "Veli", "Can", "Deniz",
    "Ece", "Elif", "Zeynep", "Mert", "Burak", "Omer", "Yusuf", "Kerem",
    "Cem", "Seda", "Cansu", "Bora", "Pelin", "Emre", "Selin", "Baris",
    "Ipek", "Onur", "Hakan", "Sibel", "Tuna", "Beste",
]


def generate_slots() -> list[Slot]:
    slots: list[Slot] = []
    start_date = date(2025, 12, 1)  # Monday
    slot_id = 1

    for day_offset in range(28):
        current_date = start_date + timedelta(days=day_offset)
        weekday = current_date.weekday()
        is_weekend = weekday >= 5
        day_type = DayType.WEEKEND if is_weekend else DayType.WEEKDAY

        if is_weekend:
            for duty in [DutyType.D, DutyType.E, DutyType.F]:
                slots.append(
                    Slot(
                        id=f"slot-{slot_id}",
                        date=current_date,
                        dutyType=duty,
                        dayType=day_type,
                        requiredCount=2,
                    )
                )
                slot_id += 1
        else:
            slots.append(
                Slot(
                    id=f"slot-{slot_id}",
                    date=current_date,
                    dutyType=DutyType.A,
                    dayType=day_type,
                    requiredCount=3,
                )
            )
            slot_id += 1
            for duty in [DutyType.B, DutyType.C]:
                slots.append(
                    Slot(
                        id=f"slot-{slot_id}",
                        date=current_date,
                        dutyType=duty,
                        dayType=day_type,
                        requiredCount=2,
                    )
                )
                slot_id += 1

    return slots


def random_history(total_min=60, total_max=110):
    total = random.randint(total_min, total_max)
    expected = random.randint(8, 12) * 8  # 8-12 dönem, base~8

    # A, B, C, Weekend, Night oranlarını rastgele dağıt
    weights = [random.randint(1, 5) for _ in range(5)]
    weight_sum = sum(weights)
    raw = [int(total * w / weight_sum) for w in weights]

    # Yuvarlama hatası için kalanları en yüksek ağırlıklara ekle
    residual = total - sum(raw)
    for i in sorted(range(5), key=lambda idx: weights[idx], reverse=True):
        if residual <= 0:
            break
        raw[i] += 1
        residual -= 1

    a, b, c, weekend, night = raw
    return total, expected, a, b, c, weekend, night


def create_users(num_old=20, num_new=25) -> list[User]:
    users: list[User] = []

    for i in range(num_old):
        name = NAMES[i % len(NAMES)] + f"_{i+1:02d}"
        total, expected, a, b, c, weekend, night = random_history()
        users.append(
            User(
                id=f"old_{i+1:02d}",
                name=name,
                email=None,
                history=UserHistory(
                    totalAllTime=total,
                    expectedTotal=expected,
                    countAAllTime=a,
                    countBAllTime=b,
                    countCAllTime=c,
                    countWeekendAllTime=weekend,
                    countNightAllTime=night,
                ),
                preferences=UserPreferences(),
            )
        )

    for i in range(num_new):
        name = NAMES[(i + num_old) % len(NAMES)] + f"_new_{i+1:02d}"
        users.append(
            User(
                id=f"new_{i+1:02d}",
                name=name,
                email=None,
                history=UserHistory(
                    totalAllTime=0,
                    expectedTotal=0,
                    countAAllTime=0,
                    countBAllTime=0,
                    countCAllTime=0,
                    countWeekendAllTime=0,
                    countNightAllTime=0,
                ),
                preferences=UserPreferences(),
            )
        )

    return users


def generate_unavailability(users: list[User], slots: list[Slot]):
    unavailability: list[Unavailability] = []
    for user in users:
        ratio = 0.12 if user.id.startswith("old_") else 0.18
        k = int(len(slots) * ratio)
        closed = random.sample(slots, k=k)
        for slot in closed:
            unavailability.append(Unavailability(userId=user.id, slotId=slot.id))
    return unavailability


def analyze(response, slots: list[Slot]):
    slot_type = {s.id: s.dutyType.value for s in slots}
    dist = defaultdict(lambda: defaultdict(int))
    for a in response.assignments:
        t = slot_type[a.slotId]
        dist[a.userId]["total"] += 1
        dist[a.userId][t] += 1
        if t in {"D", "E", "F"}:
            dist[a.userId]["weekend"] += 1
    return dist


def main():
    slots = generate_slots()
    users = create_users()
    unavailability = generate_unavailability(users, slots)

    request = ScheduleRequest(
        period=Period(
            id="dec-2025",
            name="Aralik 2025",
            startDate=date(2025, 12, 1),
            endDate=date(2025, 12, 28),
        ),
        users=users,
        slots=slots,
        unavailability=unavailability,
    )

    solver = SchedulerSolver()
    response = solver.solve(request)

    print(f"Status: {response.meta.solverStatus}")
    print(f"Base: {response.meta.base}, Min: {response.meta.minShifts}, Max: {response.meta.maxShifts}")
    print(f"Assignments: {len(response.assignments)}, Slots: {len(slots)}, Users: {len(users)}")

    dist = analyze(response, slots)

    headers = ["ID", "Total", "A", "B", "C", "D", "E", "F", "WE"]
    print("\n" + " ".join(f"{h:>6}" for h in headers))
    print("-" * 70)

    for user in sorted(users, key=lambda u: dist[u.id]["total"], reverse=True):
        d = dist[user.id]
        print(
            f"{user.id:>6} "
            f"{d['total']:>6} {d.get('A',0):>6} {d.get('B',0):>6} {d.get('C',0):>6} "
            f"{d.get('D',0):>6} {d.get('E',0):>6} {d.get('F',0):>6} {d.get('weekend',0):>6}"
        )

    # Özet
    totals = [dist[u.id]["total"] for u in users]
    print("\nTotal shifts -> min: {}, max: {}, avg: {:.2f}".format(min(totals), max(totals), sum(totals)/len(totals)))


if __name__ == "__main__":
    main()

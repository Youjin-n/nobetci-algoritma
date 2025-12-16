"""
Test per-type fairness - A/B/C/Weekend dağılımını detaylı göster
"""
import sys
import json

sys.path.insert(0, ".")

from app.services.scheduler.solver import SchedulerSolver
from app.schemas.schedule import ScheduleRequest


def main():
    # Load latest production request
    with open(r"c:\Users\Lenovo\OneDrive\Masaüstü\nobetci-v2\debug\2025-12-16_04-26-34_ao_request.json") as f:
        data = json.load(f)
    
    print("=" * 80)
    print("PER-TYPE FAIRNESS TEST")
    print("=" * 80)
    
    request = ScheduleRequest(**data)
    result = SchedulerSolver().solve(request)
    
    print(f"Status: {result.meta.solverStatus}")
    print(f"Total: Min={result.meta.minShifts}, Max={result.meta.maxShifts}")
    
    # Per-user, per-type count
    user_stats = {u.id: {"name": u.name, "A": 0, "B": 0, "C": 0, "Weekend": 0, "Total": 0} for u in request.users}
    
    slot_lookup = {s.id: s for s in request.slots}
    for a in result.assignments:
        slot = slot_lookup.get(a.slotId)
        if slot:
            uid = a.userId
            dtype = slot.dutyType
            user_stats[uid]["Total"] += 1
            
            if dtype == "A":
                user_stats[uid]["A"] += 1
            elif dtype == "B":
                user_stats[uid]["B"] += 1
            elif dtype == "C":
                user_stats[uid]["C"] += 1
            
            if dtype in ("D", "E", "F"):
                user_stats[uid]["Weekend"] += 1
    
    # Calculate expected bounds
    num_users = len(request.users)
    type_totals = {"A": 0, "B": 0, "C": 0, "Weekend": 0}
    for s in request.slots:
        seats = len(s.seats)
        if s.dutyType == "A":
            type_totals["A"] += seats
        elif s.dutyType == "B":
            type_totals["B"] += seats
        elif s.dutyType == "C":
            type_totals["C"] += seats
        if s.dutyType in ("D", "E", "F"):
            type_totals["Weekend"] += seats
    
    import math
    print("\n" + "=" * 80)
    print("EXPECTED BOUNDS (Google pattern: floor/ceil)")
    print("=" * 80)
    for cat, total in type_totals.items():
        ideal = total / num_users
        min_val = math.floor(ideal)
        max_val = math.ceil(ideal)
        print(f"{cat}: {total} slots / {num_users} users = {ideal:.2f} → min={min_val}, max={max_val}")
    
    # Print per-user stats
    print("\n" + "=" * 80)
    print(f"{'Name':<25} {'Tot':>4} {'A':>3} {'B':>3} {'C':>3} {'Wknd':>4}")
    print("-" * 45)
    for uid, stats in sorted(user_stats.items(), key=lambda x: x[1]["Total"], reverse=True):
        name = stats["name"][:24] if stats["name"] else uid[:8]
        print(f"{name:<25} {stats['Total']:>4} {stats['A']:>3} {stats['B']:>3} {stats['C']:>3} {stats['Weekend']:>4}")
    
    # Check bounds
    print("\n" + "=" * 80)
    print("ACTUAL RANGES")
    print("=" * 80)
    for cat in ["A", "B", "C", "Weekend"]:
        values = [s[cat] for s in user_stats.values()]
        actual_min = min(values)
        actual_max = max(values)
        ideal = type_totals[cat] / num_users
        expected_min = math.floor(ideal)
        expected_max = math.ceil(ideal)
        status = "✅" if actual_min >= expected_min and actual_max <= expected_max else "❌"
        print(f"{cat}: actual=[{actual_min}, {actual_max}] expected=[{expected_min}, {expected_max}] {status}")


if __name__ == "__main__":
    main()

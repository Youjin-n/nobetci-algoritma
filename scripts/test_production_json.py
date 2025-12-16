"""
Test production JSON locally to debug 9-12 range issue
"""
import sys
import json

sys.path.insert(0, ".")

from app.services.scheduler.solver import SchedulerSolver
from app.schemas.schedule import ScheduleRequest


def main():
    # Load production request
    with open(r"c:\Users\Lenovo\OneDrive\Masaüstü\nobetci-v2\debug\2025-12-16_03-05-11_ao_request.json") as f:
        data = json.load(f)
    
    print("=" * 80)
    print("PRODUCTION JSON LOCAL TEST")
    print("=" * 80)
    
    total_seats = sum(len(s["seats"]) for s in data["slots"])
    num_users = len(data["users"])
    num_slots = len(data["slots"])
    
    print(f"Users: {num_users}")
    print(f"Slots: {num_slots}")
    print(f"Total Seats: {total_seats}")
    print(f"Per User Ideal: {total_seats / num_users:.2f}")
    print(f"Base (floor): {total_seats // num_users}")
    
    # Check unavailability
    unavail_count = len(data.get("unavailability", []))
    print(f"Unavailability: {unavail_count}")
    
    print("\nSolving...")
    
    request = ScheduleRequest(**data)
    result = SchedulerSolver().solve(request)
    
    print(f"\nMeta: Status={result.meta.solverStatus}")
    print(f"Min={result.meta.minShifts}, Max={result.meta.maxShifts}, Diff={result.meta.maxShifts - result.meta.minShifts}")
    print(f"Unavailability Violations: {result.meta.unavailabilityViolations}")
    
    # Count per user
    user_counts = {}
    for assignment in result.assignments:
        uid = assignment.userId
        user_counts[uid] = user_counts.get(uid, 0) + 1
    
    # Distribution
    dist = {}
    for count in user_counts.values():
        dist[count] = dist.get(count, 0) + 1
    
    print(f"\nDistribution: {dict(sorted(dist.items()))}")
    
    # Check constraint values
    print("\n" + "=" * 80)
    print("EXPECTED RESULT")
    print("=" * 80)
    print(f"Base = {total_seats // num_users}")
    print(f"Min allowed = base - 2 = {max(0, total_seats // num_users - 2)}")
    print(f"Max allowed = base + 2 = {total_seats // num_users + 2}")


if __name__ == "__main__":
    main()

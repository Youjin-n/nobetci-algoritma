"""
Test latest production request locally with timing
"""
import sys
import json
import time

sys.path.insert(0, ".")

from app.services.scheduler.solver import SchedulerSolver
from app.schemas.schedule import ScheduleRequest


def main():
    # Load latest production request
    with open(r"c:\Users\Lenovo\OneDrive\Masaüstü\nobetci-v2\debug\2025-12-16_04-26-34_ao_request.json") as f:
        data = json.load(f)
    
    print("=" * 80)
    print("LATEST PRODUCTION REQUEST - LOCAL TEST")
    print("=" * 80)
    
    total_seats = sum(len(s["seats"]) for s in data["slots"])
    num_users = len(data["users"])
    
    print(f"Users: {num_users}")
    print(f"Total Seats: {total_seats}")
    print(f"Per User Ideal: {total_seats / num_users:.2f}")
    
    print("\nSolving...")
    
    start = time.perf_counter()
    request = ScheduleRequest(**data)
    result = SchedulerSolver().solve(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    print(f"\nMeta: Status={result.meta.solverStatus}")
    print(f"Min={result.meta.minShifts}, Max={result.meta.maxShifts}, Diff={result.meta.maxShifts - result.meta.minShifts}")
    print(f"Local Solve Time: {elapsed_ms:.0f}ms")
    print(f"Production Solve Time: 65016ms")
    
    # Distribution
    user_counts = {}
    for assignment in result.assignments:
        uid = assignment.userId
        user_counts[uid] = user_counts.get(uid, 0) + 1
    
    dist = {}
    for count in user_counts.values():
        dist[count] = dist.get(count, 0) + 1
    
    print(f"\nDistribution: {dict(sorted(dist.items()))}")


if __name__ == "__main__":
    main()

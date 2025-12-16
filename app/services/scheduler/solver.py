"""
Main Scheduler Solver

OR-Tools CP-SAT kullanarak nöbet optimizasyonu.
Yeni SPEC'e göre:
- Hard constraints: Coverage, yasak geçişler, base+3, günde 1 nöbet
- Soft constraints: Penalty sistemi (Level 1-5)
- Zor slot heuristiği: Round-robin dağılım
"""

import time
from collections import defaultdict
from datetime import date
from typing import Literal

from ortools.sat.python import cp_model

from app.core.config import Settings, get_settings
from app.schemas.schedule import (
    Assignment,
    ScheduleMeta,
    ScheduleRequest,
    ScheduleResponse,
    SeatRole,
)

from .constraints import HardConstraintBuilder, is_night_duty, is_weekend_duty
from .models import (
    AssignmentResult,
    InternalSeat,
    InternalSlot,
    InternalUser,
    SchedulerContext,
    SolverResult,
)
from .score import PenaltyBuilder, calculate_desk_operator_distribution


class SchedulerSolver:
    """
    Ana nöbet çözücü sınıfı.

    OR-Tools CP-SAT ile:
    - Hard constraint'ler garanti altında
    - Soft penalty'ler minimize edilir
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def solve(self, request: ScheduleRequest) -> ScheduleResponse:
        """
        Ana çözüm metodu.

        1. Request'i internal modellere dönüştür
        2. CP-SAT modelini oluştur (hard + soft)
        3. Çöz
        4. Desk/Operator ata (A slotları için)
        5. Response oluştur
        """
        start_time = time.perf_counter()

        # 1. Context oluştur
        context = self._build_context(request)

        # 2. Çöz
        result = self._solve_with_cpsat(context)

        # 3. A nöbetleri için desk/operator ataması
        result = self._assign_desk_operator_roles(result, context)

        # 4. Response oluştur
        solve_time_ms = (time.perf_counter() - start_time) * 1000

        return self._build_response(result, context, solve_time_ms)

    def _build_context(self, request: ScheduleRequest) -> SchedulerContext:
        """Request'ten SchedulerContext oluştur"""
        context = SchedulerContext(users=[], slots=[])

        # Users
        for idx, user in enumerate(request.users):
            internal_user = InternalUser(
                id=user.id,
                name=user.name,
                index=idx,
                history_total=user.history.totalAllTime,
                history_expected=user.history.expectedTotal,
                history_a=user.history.countAAllTime,
                history_b=user.history.countBAllTime,
                history_c=user.history.countCAllTime,
                history_weekend=user.history.countWeekendAllTime,
                history_night=user.history.countNightAllTime,
                likes_night=user.likesNight,
                dislikes_weekend=user.dislikesWeekend,
            )
            context.users.append(internal_user)
            context.user_id_to_index[user.id] = idx

        # Slots with seats
        for idx, slot in enumerate(request.slots):
            # seats -> InternalSeat dönüşümü
            internal_seats = []
            for seat_idx, seat in enumerate(slot.seats):
                internal_seat = InternalSeat(
                    id=seat.id,
                    index=seat_idx,
                    role=seat.role.value if seat.role else None,
                )
                internal_seats.append(internal_seat)
                context.seat_id_to_slot_index[seat.id] = idx
                context.all_seats.append(internal_seat)

            internal_slot = InternalSlot(
                id=slot.id,
                index=idx,
                date=slot.slot_date,
                duty_type=slot.dutyType.value,
                day_type=slot.dayType.value,
                required_count=slot.requiredCount,
                seats=internal_seats,
            )
            context.slots.append(internal_slot)
            context.slot_id_to_index[slot.id] = idx

            # Tarih bazlı grupla
            if slot.slot_date not in context.date_to_slot_indices:
                context.date_to_slot_indices[slot.slot_date] = []
            context.date_to_slot_indices[slot.slot_date].append(idx)

        # Unavailability
        for unavail in request.unavailability:
            user_idx = context.user_id_to_index.get(unavail.userId)
            slot_idx = context.slot_id_to_index.get(unavail.slotId)
            if user_idx is not None and slot_idx is not None:
                context.unavailability_set.add((user_idx, slot_idx))
                # Slot zorluk skoru için
                context.slot_unavailability_count[slot_idx] = (
                    context.slot_unavailability_count.get(slot_idx, 0) + 1
                )

        # --- Unavailability Fairness: blocked_count hesapla ---
        # Categories: "A", "B", "C", "Weekend" (D+E+F combined)
        def _get_category(duty_type: str) -> str:
            if duty_type in ("D", "E", "F"):
                return "Weekend"
            return duty_type  # A, B, C as-is

        # Her kullanıcı için kategori bazında blocked_count başlat
        for user in context.users:
            context.blocked_count_per_category[user.index] = {
                "A": 0, "B": 0, "C": 0, "Weekend": 0
            }

        # Her unavailability için ilgili kategoriye ekle
        for user_idx, slot_idx in context.unavailability_set:
            slot = context.slots[slot_idx]
            category = _get_category(slot.duty_type)
            context.blocked_count_per_category[user_idx][category] += 1

        # Her kategoride max blocked_count hesapla
        context.max_blocked_per_category = {"A": 0, "B": 0, "C": 0, "Weekend": 0}
        for user_idx, cat_counts in context.blocked_count_per_category.items():
            for cat, count in cat_counts.items():
                if count > context.max_blocked_per_category[cat]:
                    context.max_blocked_per_category[cat] = count

        # TOPLAM slot kapama sayısı hesapla (tüm kategoriler)
        # Çok kapatan → zor slotlara atanır (gerçek hayat cezası)
        for user in context.users:
            total = sum(context.blocked_count_per_category[user.index].values())
            context.total_blocked_count[user.index] = total
            if total > context.max_total_blocked:
                context.max_total_blocked = total

        # Base hesapla
        context.total_seats = sum(s.required_count for s in context.slots)
        if context.users:
            context.base_shifts = context.total_seats // len(context.users)

        # Per-type fairness ideals hesapla (Google pattern)
        # Her tip için: min = floor(total/n), max = ceil(total/n)
        num_users = len(context.users)
        if num_users > 0:
            # Her tip için toplam slot sayısını hesapla
            type_totals = {"A": 0, "B": 0, "C": 0, "Weekend": 0}
            for slot in context.slots:
                duty_type = slot.duty_type
                seats = slot.required_count
                
                if duty_type == "A":
                    type_totals["A"] += seats
                elif duty_type == "B":
                    type_totals["B"] += seats
                elif duty_type == "C":
                    type_totals["C"] += seats
                
                # Weekend = D + E + F
                if duty_type in ("D", "E", "F"):
                    type_totals["Weekend"] += seats
            
            # Min/max hesapla
            import math
            for cat, total in type_totals.items():
                ideal = total / num_users
                context.type_ideals[cat] = {
                    "total": total,
                    "min": math.floor(ideal),
                    "max": math.ceil(ideal),
                }

        return context

    def _solve_with_cpsat(self, context: SchedulerContext) -> SolverResult:
        """OR-Tools CP-SAT ile çöz"""
        model = cp_model.CpModel()
        warnings: list[str] = []

        num_users = len(context.users)
        num_slots = len(context.slots)

        if num_users == 0 or num_slots == 0:
            return SolverResult(
                assignments=[],
                status="TRIVIAL",
                solve_time_ms=0,
                warnings=["No users or slots provided."],
                base=0,
                max_shifts=0,
                min_shifts=0,
            )

        # --- Karar Değişkenleri ---
        # x[u, s] = 1 ise user u, slot s'e atanmış
        x: dict[tuple[int, int], cp_model.IntVar] = {}
        for user in context.users:
            for slot in context.slots:
                x[user.index, slot.index] = model.NewBoolVar(
                    f"x_u{user.index}_s{slot.index}"
                )

        # --- Hard Constraints ---
        # max_allowed = base + 2 (base+3 yasak)
        max_allowed = context.base_shifts + 2

        hard_builder = HardConstraintBuilder(model, context, x)
        hard_builder.add_all_hard_constraints(max_allowed)

        # --- User shift count değişkenleri ---
        user_shift_counts: dict[int, cp_model.IntVar] = {}
        for user in context.users:
            count_var = model.NewIntVar(0, num_slots, f"total_{user.index}")
            user_vars = [x[user.index, slot.index] for slot in context.slots]
            model.Add(count_var == sum(user_vars))
            user_shift_counts[user.index] = count_var

        # --- Soft Constraints / Penalties ---
        penalty_builder = PenaltyBuilder(model, context, x, self.settings)
        penalty_builder.build_all_penalties(user_shift_counts)

        # Objective: minimize total penalty
        objective = penalty_builder.get_total_objective()
        model.Minimize(objective)

        # --- SOLUTION HINT: Dengeli başlangıç noktası ---
        # Render free tier yavaş CPU için, solver'a iyi bir başlangıç ver
        # Her kullanıcıya base veya base+1 shift atayarak başla
        num_users = len(context.users)
        base = context.base_shifts
        remainder = context.total_seats - (base * num_users)  # Kaç kişi base+1 alacak
        
        # Kullanıcılara round-robin atama yap (hint olarak)
        user_target = {}
        for i, user in enumerate(context.users):
            if i < remainder:
                user_target[user.index] = base + 1
            else:
                user_target[user.index] = base
        
        # Her slot için round-robin atama hint'i
        slot_assignments = {slot.index: [] for slot in context.slots}
        user_counts = {user.index: 0 for user in context.users}
        
        for slot in sorted(context.slots, key=lambda s: s.date):
            needed = slot.required_count
            # En az atama yapılan ve target'a ulaşmamış kullanıcıları seç
            available_users = sorted(
                [u for u in context.users if user_counts[u.index] < user_target[u.index]],
                key=lambda u: user_counts[u.index]
            )
            for i in range(min(needed, len(available_users))):
                slot_assignments[slot.index].append(available_users[i].index)
                user_counts[available_users[i].index] += 1
        
        # Hint olarak model'e ekle
        for user in context.users:
            for slot in context.slots:
                if user.index in slot_assignments[slot.index]:
                    model.AddHint(x[user.index, slot.index], 1)
                else:
                    model.AddHint(x[user.index, slot.index], 0)

        # --- Çöz ---
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.settings.scheduler_time_limit_seconds
        solver.parameters.random_seed = self.settings.scheduler_random_seed
        solver.parameters.num_search_workers = 4

        status = solver.Solve(model)
        status_name = solver.StatusName(status)

        # --- Sonuç Çıkar ---
        assignments: list[AssignmentResult] = []

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            # Atamaları çıkar - her slot için atanan user'ları seat'lere eşleştir
            for slot in context.slots:
                slot_users = []
                for user in context.users:
                    if solver.Value(x[user.index, slot.index]) == 1:
                        slot_users.append(user)
                
                # Her atanan user'ı bir seat'e eşle
                for seat_idx, user in enumerate(slot_users):
                    seat = slot.seats[seat_idx] if seat_idx < len(slot.seats) else None
                    seat_id = seat.id if seat else f"{slot.id}-seat-{seat_idx}"
                    
                    assignments.append(
                        AssignmentResult(
                            slot_id=slot.id,
                            seat_id=seat_id,
                            user_id=user.id,
                        )
                    )

            # İstatistikleri hesapla
            user_counts = {
                u.index: solver.Value(user_shift_counts[u.index])
                for u in context.users
            }
            max_shifts = max(user_counts.values()) if user_counts else 0
            min_shifts = min(user_counts.values()) if user_counts else 0

            # base+2'ye çıkanlar (safeLimit = base+1)
            safe_limit = context.base_shifts + 1
            users_at_base_plus_2 = sum(
                1 for count in user_counts.values() if count > safe_limit
            )

            # Unavailability violations
            unavail_violations = sum(
                1 for (u_idx, s_idx) in context.unavailability_set
                if solver.Value(x[u_idx, s_idx]) == 1
            )

            # 3 gün üst üste olanlar
            consec_3_users = self._count_consecutive_3_day_users(
                assignments, context
            )

            # Warnings oluştur
            if unavail_violations > 0:
                warnings.append(
                    f"{unavail_violations} assignment(s) had to ignore user unavailability."
                )

            if users_at_base_plus_2 > 0:
                warnings.append(
                    f"{users_at_base_plus_2} user(s) were pushed to base+2 total shifts."
                )

            if consec_3_users > 0:
                warnings.append(
                    f"{consec_3_users} user(s) had 3+ consecutive days with shifts."
                )

        else:
            warnings.append(f"Solver status: {status_name}. No feasible solution found.")
            max_shifts = 0
            min_shifts = 0
            users_at_base_plus_2 = 0
            unavail_violations = 0

        return SolverResult(
            assignments=assignments,
            status=status_name,
            solve_time_ms=solver.WallTime() * 1000,
            warnings=warnings,
            base=context.base_shifts,
            max_shifts=max_shifts,
            min_shifts=min_shifts,
            users_at_base_plus_2=users_at_base_plus_2,
            unavailability_violations=unavail_violations,
        )

    def _count_consecutive_3_day_users(
        self,
        assignments: list[AssignmentResult],
        context: SchedulerContext,
    ) -> int:
        """3 gün üst üste nöbet tutan kullanıcı sayısını hesapla"""
        # Kullanıcı bazında hangi günlerde nöbet var
        user_dates: dict[str, set[date]] = defaultdict(set)

        for assignment in assignments:
            slot_idx = context.slot_id_to_index.get(assignment.slot_id)
            if slot_idx is not None:
                slot = context.slots[slot_idx]
                user_dates[assignment.user_id].add(slot.date)

        # Her kullanıcı için 3 ardışık gün kontrolü
        count = 0
        from datetime import timedelta

        for user_id, dates in user_dates.items():
            sorted_dates = sorted(dates)
            has_consec_3 = False

            for i in range(len(sorted_dates) - 2):
                d1, d2, d3 = sorted_dates[i], sorted_dates[i + 1], sorted_dates[i + 2]
                if (d2 - d1).days == 1 and (d3 - d2).days == 1:
                    has_consec_3 = True
                    break

            if has_consec_3:
                count += 1

        return count

    def _assign_desk_operator_roles(
        self,
        result: SolverResult,
        context: SchedulerContext,
    ) -> SolverResult:
        """
        A nöbetleri için desk/operator rolü ata.
        Kullanıcıların tarihsel + current rol sayılarına göre dengeli ata.
        """
        # A slotlarını grupla
        a_slot_assignments: dict[str, list[AssignmentResult]] = defaultdict(list)
        for assignment in result.assignments:
            slot_idx = context.slot_id_to_index.get(assignment.slot_id)
            if slot_idx is not None:
                slot = context.slots[slot_idx]
                if slot.duty_type == "A":
                    a_slot_assignments[assignment.slot_id].append(assignment)

        # Geçici sayaçlar (bu dönem için)
        current_desk: dict[str, int] = defaultdict(int)
        current_operator: dict[str, int] = defaultdict(int)

        for slot_id, slot_assignments in a_slot_assignments.items():
            count = len(slot_assignments)
            desk_needed, operator_needed = calculate_desk_operator_distribution(count)

            # Desk için öncelik: daha az desk almış
            def desk_priority(a: AssignmentResult) -> tuple[int, int]:
                user_idx = context.user_id_to_index.get(a.user_id, 0)
                user = context.users[user_idx] if user_idx < len(context.users) else None
                history = user.history_desk if user else 0
                current = current_desk[a.user_id]
                return (history + current, current)

            # Operator için öncelik: daha az operator almış
            def operator_priority(a: AssignmentResult) -> tuple[int, int]:
                user_idx = context.user_id_to_index.get(a.user_id, 0)
                user = context.users[user_idx] if user_idx < len(context.users) else None
                history = user.history_operator if user else 0
                current = current_operator[a.user_id]
                return (history + current, current)

            # Desk ata
            sorted_for_desk = sorted(slot_assignments, key=desk_priority)
            for i, assignment in enumerate(sorted_for_desk):
                if i < desk_needed:
                    assignment.seat_role = "DESK"
                    current_desk[assignment.user_id] += 1

            # Operator ata (desk olmayanlar)
            remaining = [a for a in slot_assignments if a.seat_role is None]
            sorted_for_operator = sorted(remaining, key=operator_priority)
            for i, assignment in enumerate(sorted_for_operator):
                if i < operator_needed:
                    assignment.seat_role = "OPERATOR"
                    current_operator[assignment.user_id] += 1

        return result

    def _build_response(
        self,
        result: SolverResult,
        context: SchedulerContext,
        solve_time_ms: float,
    ) -> ScheduleResponse:
        """SolverResult'u ScheduleResponse'a dönüştür"""

        # isExtra: base+1'i aşan atamaları işaretle
        user_assignment_order: dict[str, int] = defaultdict(int)
        safe_limit = context.base_shifts + 1

        assignments = []
        for assignment in result.assignments:
            user_assignment_order[assignment.user_id] += 1
            current_count = user_assignment_order[assignment.user_id]

            # base+1'i aşan atamalar isExtra
            is_extra = current_count > safe_limit

            seat_role = None
            if assignment.seat_role == "DESK":
                seat_role = SeatRole.DESK
            elif assignment.seat_role == "OPERATOR":
                seat_role = SeatRole.OPERATOR

            assignments.append(
                Assignment(
                    slotId=assignment.slot_id,
                    seatId=assignment.seat_id,
                    userId=assignment.user_id,
                    seatRole=seat_role,
                    isExtra=is_extra,
                )
            )

        meta = ScheduleMeta(
            base=result.base,
            maxShifts=result.max_shifts,
            minShifts=result.min_shifts,
            totalSlots=len(context.slots),
            totalAssignments=len(assignments),
            usersAtBasePlus2=result.users_at_base_plus_2,
            unavailabilityViolations=result.unavailability_violations,
            warnings=result.warnings,
            solverStatus=result.status,
            solveTimeMs=solve_time_ms,
        )

        return ScheduleResponse(assignments=assignments, meta=meta)

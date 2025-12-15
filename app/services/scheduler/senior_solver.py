"""
Senior Scheduler Solver

Nöbetçi Asistanlar için A nöbetinin sabah/akşam segmentlerini dağıtır.
OR-Tools CP-SAT ile constraint programming yaklaşımı.

HARD CONSTRAINTS:
- Coverage: Her slot requiredCount kadar dolu olmalı
- Base+3 yasak: totalShifts <= base + 2
- Günde max 2 segment (sabah + akşam)

SOFT PENALTIES:
- Level 1 (100k): Base+2'ye çıkma
- Level 2 (10k/7k): Unavailability ihlali, 3+ gün üst üste
- Level 3 (1k): Fairness - yarım A sayısı eşitliği, geçmiş denge
- Level 4 (100): Haftalık yığılma, aynı gün sabah+akşam
- Level 5 (10): Sabah/akşam tercihleri
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from ortools.sat.python import cp_model

from app.core.config import Settings, get_settings
from app.schemas.schedule import Assignment, ScheduleMeta, ScheduleResponse
from app.schemas.schedule_senior import SeniorScheduleRequest, SeniorSeat


# --- Internal Models ---

@dataclass
class SeniorInternalUser:
    """Internal user representation"""
    id: str
    name: str
    index: int
    history_total: int = 0
    history_a: int = 0
    history_morning: int = 0
    history_evening: int = 0



@dataclass
class SeniorInternalSlot:
    """Internal slot representation"""
    id: str
    index: int
    date: date
    segment: str  # "MORNING" or "EVENING"
    required_count: int
    seats: list[SeniorSeat] = field(default_factory=list)


@dataclass
class SeniorContext:
    """Solver context"""
    users: list[SeniorInternalUser]
    slots: list[SeniorInternalSlot]
    user_id_to_index: dict[str, int] = field(default_factory=dict)
    slot_id_to_index: dict[str, int] = field(default_factory=dict)
    unavailability_set: set[tuple[int, int]] = field(default_factory=set)
    date_to_slot_indices: dict[date, list[int]] = field(default_factory=dict)
    slot_unavailability_count: dict[int, int] = field(default_factory=dict)
    total_seats: int = 0
    base_shifts: int = 0
    period_start: date | None = None


@dataclass
class SeniorAssignmentResult:
    """Single assignment result"""
    slot_id: str
    seat_id: str
    user_id: str
    seat_role: str | None = None  # "DESK" or "OPERATOR"


@dataclass
class SeniorSolverResult:
    """Solver result"""
    assignments: list[SeniorAssignmentResult]
    status: str
    solve_time_ms: float
    warnings: list[str]
    base: int
    max_shifts: int
    min_shifts: int
    users_at_base_plus_2: int = 0
    unavailability_violations: int = 0
    consecutive_3_users: int = 0


# --- Penalty Constants (Güncellenmiş Hiyerarşi) ---

# Level 1 – Çok ağır soft
PENALTY_UNAVAILABILITY = 200_000        # EN ağır soft - müsaitlik ihlali
PENALTY_ABOVE_IDEAL_STRONG = 120_000    # ideal + 2 ve üstü
PENALTY_BELOW_IDEAL_STRONG = 140_000    # ideal - 2 ve altı
PENALTY_ZERO_SHIFTS = 80_000            # 0 nöbet kalma

# Level 2 – Ağır
PENALTY_CONSECUTIVE_3_DAYS = 7_000      # 3 gün üst üste

# Level 3 – Fairness
PENALTY_IDEAL_SOFT = 4_000              # |diff| == 1 için hafif ceza
PENALTY_FAIRNESS_HISTORY = 3_000        # Tarihsel denge (düşürüldü)
PENALTY_FAIRNESS_HALF_A = 1_000         # Yarım A sayısı eşitliği

# Level 4 – Konfor
PENALTY_WEEKLY_CLUSTER = 100            # Haftalık yığılma
PENALTY_FULL_DAY = 100                  # Aynı gün sabah+akşam

# --- Helper Functions ---

def get_week_index(slot_date: date, period_start: date) -> int:
    """Slot'un dönem içindeki hafta indeksini hesapla"""
    days_diff = (slot_date - period_start).days
    return days_diff // 7


def get_senior_desk_operator_count(total_people: int) -> tuple[int, int]:
    """
    NA için DESK/OPERATOR sayısını hesapla.
    
    Kurallar:
    - 1 kişi: 0 DESK, 1 OPERATOR
    - 2 kişi: 1 DESK, 1 OPERATOR  
    - 3 kişi: 2 DESK, 1 OPERATOR
    - 4+ kişi: (n-1) DESK, 1 OPERATOR (genel kural)
    
    Returns:
        (desk_count, operator_count)
    """
    if total_people <= 0:
        return (0, 0)
    if total_people == 1:
        return (0, 1)
    # 2+ kişi için: hep 1 OPERATOR, geri kalan DESK
    return (total_people - 1, 1)


# --- Main Solver ---

class SeniorSchedulerSolver:
    """
    Nöbetçi Asistan nöbet çözücüsü.

    Sadece A nöbetinin sabah/akşam segmentlerini dağıtır.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def solve(self, request: SeniorScheduleRequest) -> ScheduleResponse:
        """Ana çözüm metodu"""
        start_time = time.perf_counter()

        # 1. Context oluştur
        context = self._build_context(request)

        # 2. Çöz
        result = self._solve_with_cpsat(context)

        # 3. Response'a dönüştür
        end_time = time.perf_counter()
        solve_time_ms = (end_time - start_time) * 1000

        return self._build_response(result, context, solve_time_ms)

    def _build_context(self, request: SeniorScheduleRequest) -> SeniorContext:
        """Request'ten internal context oluştur"""
        context = SeniorContext(users=[], slots=[])
        context.period_start = request.period.startDate

        # Users
        for idx, user in enumerate(request.users):
            internal_user = SeniorInternalUser(
                id=user.id,
                name=user.name,
                index=idx,
                history_total=user.history.totalAllTime,
                history_a=user.history.countAAllTime,
                history_morning=user.history.countMorningAllTime,
                history_evening=user.history.countEveningAllTime)
            context.users.append(internal_user)
            context.user_id_to_index[user.id] = idx

        # Slots
        for idx, slot in enumerate(request.slots):
            internal_slot = SeniorInternalSlot(
                id=slot.id,
                index=idx,
                date=slot.slot_date,
                segment=slot.segment.value,
                required_count=len(slot.seats),
                seats=slot.seats,
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
                context.slot_unavailability_count[slot_idx] = (
                    context.slot_unavailability_count.get(slot_idx, 0) + 1
                )

        # Base hesapla
        context.total_seats = sum(s.required_count for s in context.slots)
        if context.users:
            context.base_shifts = context.total_seats // len(context.users)

        return context

    def _solve_with_cpsat(self, context: SeniorContext) -> SeniorSolverResult:
        """OR-Tools CP-SAT ile çöz"""
        model = cp_model.CpModel()
        warnings: list[str] = []

        num_users = len(context.users)
        num_slots = len(context.slots)

        if num_users == 0 or num_slots == 0:
            return SeniorSolverResult(
                assignments=[],
                status="TRIVIAL",
                solve_time_ms=0,
                warnings=["No users or slots provided."],
                base=0,
                max_shifts=0,
                min_shifts=0,
            )

        # --- Karar Değişkenleri ---
        x: dict[tuple[int, int], cp_model.IntVar] = {}
        for user in context.users:
            for slot in context.slots:
                x[user.index, slot.index] = model.NewBoolVar(
                    f"x_u{user.index}_s{slot.index}"
                )

        # --- HARD CONSTRAINTS ---
        max_allowed = context.base_shifts + 2

        # 1. Coverage: Her slot requiredCount kadar dolu
        for slot in context.slots:
            slot_vars = [x[u.index, slot.index] for u in context.users]
            model.Add(sum(slot_vars) == slot.required_count)

        # 2. Base+2 hard limit (base+3 yasak)
        for user in context.users:
            user_vars = [x[user.index, s.index] for s in context.slots]
            model.Add(sum(user_vars) <= max_allowed)

        # 3. Günde max 2 segment (sabah + akşam = max 2)
        for slot_date, slot_indices in context.date_to_slot_indices.items():
            for user in context.users:
                day_vars = [x[user.index, si] for si in slot_indices]
                model.Add(sum(day_vars) <= 2)

        # --- USER SHIFT COUNT DEĞİŞKENLERİ ---
        user_shift_counts: dict[int, cp_model.IntVar] = {}
        for user in context.users:
            count_var = model.NewIntVar(0, num_slots, f"total_{user.index}")
            user_vars = [x[user.index, slot.index] for slot in context.slots]
            model.Add(count_var == sum(user_vars))
            user_shift_counts[user.index] = count_var

        # --- SOFT PENALTIES ---
        penalties: list[cp_model.LinearExpr] = []

        # Level 1a: Unavailability ihlali - EN AĞIR (200_000)
        for user_idx, slot_idx in context.unavailability_set:
            penalties.append(x[user_idx, slot_idx] * PENALTY_UNAVAILABILITY)

        # Level 1b: ideal + 2 üstüne çıkma cezası (120_000)
        safe_limit = context.base_shifts + 1
        for user in context.users:
            excess = model.NewIntVar(0, max_allowed - safe_limit, f"excess_{user.index}")
            model.AddMaxEquality(excess, [user_shift_counts[user.index] - safe_limit, 0])
            penalties.append(excess * PENALTY_ABOVE_IDEAL_STRONG)

        # Level 2: 3+ gün üst üste yarım A (7_000)
        self._add_consecutive_days_penalty(model, context, x, penalties)

        # Level 3a: Yarım A sayısı fairness - SİMETRİK (1_000)
        # Hem fazla hem eksik cezalandırılır
        if num_users > 1:
            ideal = context.total_seats // num_users
            for user in context.users:
                diff = model.NewIntVar(-max_allowed, max_allowed, f"fair_diff_{user.index}")
                model.Add(diff == user_shift_counts[user.index] - ideal)
                abs_diff = model.NewIntVar(0, max_allowed, f"fair_abs_{user.index}")
                model.AddAbsEquality(abs_diff, diff)
                penalties.append(abs_diff * PENALTY_FAIRNESS_HALF_A)

        # Level 3b: Geçmiş A sayısı ile denge - SİMETRİK (3_000)
        if num_users > 1:
            avg_history = sum(u.history_a for u in context.users) // num_users
            for user in context.users:
                # longTermA = history + current
                long_term = model.NewIntVar(0, 10000, f"longterm_{user.index}")
                model.Add(long_term == user.history_a + user_shift_counts[user.index])
                diff = model.NewIntVar(-1000, 1000, f"hist_diff_{user.index}")
                model.Add(diff == long_term - avg_history)
                abs_diff = model.NewIntVar(0, 1000, f"hist_abs_{user.index}")
                model.AddAbsEquality(abs_diff, diff)
                penalties.append(abs_diff * PENALTY_FAIRNESS_HISTORY)

        # Level 4a: Haftalık yığılma (100)
        self._add_weekly_clustering_penalty(model, context, x, penalties)

        # Level 4b: Aynı gün sabah+akşam - KALDIRILDI
        # Kullanıcılar tam gün çalışmak İSTİYOR, cezalandırma yok
        # self._add_full_day_penalty(model, context, x, penalties)

        # Objective
        model.Minimize(sum(penalties))

        # --- ÇÖZ ---
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.settings.scheduler_time_limit_seconds
        solver.parameters.random_seed = self.settings.scheduler_random_seed
        solver.parameters.num_search_workers = 4

        status = solver.Solve(model)
        status_name = solver.StatusName(status)

        # --- Sonuç Çıkar ---
        assignments: list[SeniorAssignmentResult] = []

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for slot in context.slots:
                slot_users = []
                for user in context.users:
                    if solver.Value(x[user.index, slot.index]) == 1:
                        slot_users.append(user)
                
                # Assign seats with DESK/OPERATOR roles
                total_people = len(slot_users)
                desk_count, _ = get_senior_desk_operator_count(total_people)
                
                for seat_idx, user in enumerate(slot_users):
                    seat = slot.seats[seat_idx] if seat_idx < len(slot.seats) else None
                    seat_id = seat.id if seat else f"{slot.id}-seat-{seat_idx}"
                    
                    # İlk desk_count kişi DESK, geri kalanlar OPERATOR
                    seat_role = "DESK" if seat_idx < desk_count else "OPERATOR"
                    
                    assignments.append(
                        SeniorAssignmentResult(
                            slot_id=slot.id,
                            seat_id=seat_id,
                            user_id=user.id,
                            seat_role=seat_role,
                        )
                    )

            # İstatistikler
            user_counts = {
                u.index: solver.Value(user_shift_counts[u.index])
                for u in context.users
            }
            max_shifts = max(user_counts.values()) if user_counts else 0
            min_shifts = min(user_counts.values()) if user_counts else 0

            users_at_base_plus_2 = sum(
                1 for count in user_counts.values() if count > safe_limit
            )

            unavail_violations = sum(
                1 for (u_idx, s_idx) in context.unavailability_set
                if solver.Value(x[u_idx, s_idx]) == 1
            )

            consec_3_users = self._count_consecutive_3_day_users(assignments, context)

            # Warnings
            if unavail_violations > 0:
                warnings.append(
                    f"{unavail_violations} assignment(s) had to ignore unavailability for nöbetçi asistanlar."
                )
            if users_at_base_plus_2 > 0:
                warnings.append(
                    f"{users_at_base_plus_2} nöbetçi asistan were pushed to base+2 total half A shifts."
                )
            if consec_3_users > 0:
                warnings.append(
                    f"{consec_3_users} nöbetçi asistan had 3+ consecutive days with half A shifts."
                )

        else:
            warnings.append(f"Solver status: {status_name}. No feasible solution found.")
            max_shifts = 0
            min_shifts = 0
            users_at_base_plus_2 = 0
            unavail_violations = 0
            consec_3_users = 0

        return SeniorSolverResult(
            assignments=assignments,
            status=status_name,
            solve_time_ms=solver.WallTime() * 1000,
            warnings=warnings,
            base=context.base_shifts,
            max_shifts=max_shifts,
            min_shifts=min_shifts,
            users_at_base_plus_2=users_at_base_plus_2,
            unavailability_violations=unavail_violations,
            consecutive_3_users=consec_3_users,
        )

    def _add_consecutive_days_penalty(
        self,
        model: cp_model.CpModel,
        context: SeniorContext,
        x: dict[tuple[int, int], cp_model.IntVar],
        penalties: list,
    ) -> None:
        """3+ gün üst üste nöbet cezası (Level 2: 7_000)"""
        sorted_dates = sorted(context.date_to_slot_indices.keys())
        if len(sorted_dates) < 3:
            return

        for user in context.users:
            # Her 3 ardışık gün penceresi için
            for i in range(len(sorted_dates) - 2):
                d1, d2, d3 = sorted_dates[i], sorted_dates[i + 1], sorted_dates[i + 2]

                # Gerçekten ardışık mı?
                if (d2 - d1).days != 1 or (d3 - d2).days != 1:
                    continue

                # Her günde en az 1 segment var mı?
                day1_vars = [x[user.index, si] for si in context.date_to_slot_indices[d1]]
                day2_vars = [x[user.index, si] for si in context.date_to_slot_indices[d2]]
                day3_vars = [x[user.index, si] for si in context.date_to_slot_indices[d3]]

                has_day1 = model.NewBoolVar(f"has_d1_{user.index}_{i}")
                has_day2 = model.NewBoolVar(f"has_d2_{user.index}_{i}")
                has_day3 = model.NewBoolVar(f"has_d3_{user.index}_{i}")

                model.Add(sum(day1_vars) >= 1).OnlyEnforceIf(has_day1)
                model.Add(sum(day1_vars) == 0).OnlyEnforceIf(has_day1.Not())
                model.Add(sum(day2_vars) >= 1).OnlyEnforceIf(has_day2)
                model.Add(sum(day2_vars) == 0).OnlyEnforceIf(has_day2.Not())
                model.Add(sum(day3_vars) >= 1).OnlyEnforceIf(has_day3)
                model.Add(sum(day3_vars) == 0).OnlyEnforceIf(has_day3.Not())

                # 3 gün üst üste = has_day1 AND has_day2 AND has_day3
                all_three = model.NewBoolVar(f"consec3_{user.index}_{i}")
                model.AddBoolAnd([has_day1, has_day2, has_day3]).OnlyEnforceIf(all_three)
                model.AddBoolOr([
                    has_day1.Not(), has_day2.Not(), has_day3.Not()
                ]).OnlyEnforceIf(all_three.Not())

                penalties.append(all_three * PENALTY_CONSECUTIVE_3_DAYS)

    def _add_weekly_clustering_penalty(
        self,
        model: cp_model.CpModel,
        context: SeniorContext,
        x: dict[tuple[int, int], cp_model.IntVar],
        penalties: list,
    ) -> None:
        """Haftalık yığılma cezası (Level 4: 100)"""
        if context.period_start is None:
            return

        # Hafta bazlı slot grupla
        week_slots: dict[int, list[int]] = defaultdict(list)
        for slot in context.slots:
            week_idx = get_week_index(slot.date, context.period_start)
            week_slots[week_idx].append(slot.index)

        for user in context.users:
            for week_idx, slot_indices in week_slots.items():
                week_vars = [x[user.index, si] for si in slot_indices]
                week_count = model.NewIntVar(0, len(slot_indices), f"week_{week_idx}_{user.index}")
                model.Add(week_count == sum(week_vars))

                # >2 ise ceza
                excess = model.NewIntVar(0, len(slot_indices), f"week_exc_{week_idx}_{user.index}")
                model.AddMaxEquality(excess, [week_count - 2, 0])
                penalties.append(excess * PENALTY_WEEKLY_CLUSTER)

    def _add_full_day_penalty(
        self,
        model: cp_model.CpModel,
        context: SeniorContext,
        x: dict[tuple[int, int], cp_model.IntVar],
        penalties: list,
    ) -> None:
        """Aynı gün sabah+akşam cezası (Level 4: 100)"""
        for slot_date, slot_indices in context.date_to_slot_indices.items():
            if len(slot_indices) < 2:
                continue

            # Sabah ve akşam slotlarını bul
            morning_slots = [
                si for si in slot_indices
                if context.slots[si].segment == "MORNING"
            ]
            evening_slots = [
                si for si in slot_indices
                if context.slots[si].segment == "EVENING"
            ]

            if not morning_slots or not evening_slots:
                continue

            for user in context.users:
                # Sabahta var mı?
                has_morning = model.NewBoolVar(f"morn_{user.index}_{slot_date}")
                morning_vars = [x[user.index, si] for si in morning_slots]
                model.Add(sum(morning_vars) >= 1).OnlyEnforceIf(has_morning)
                model.Add(sum(morning_vars) == 0).OnlyEnforceIf(has_morning.Not())

                # Akşamda var mı?
                has_evening = model.NewBoolVar(f"eve_{user.index}_{slot_date}")
                evening_vars = [x[user.index, si] for si in evening_slots]
                model.Add(sum(evening_vars) >= 1).OnlyEnforceIf(has_evening)
                model.Add(sum(evening_vars) == 0).OnlyEnforceIf(has_evening.Not())

                # İkisi birden varsa ceza
                both = model.NewBoolVar(f"both_{user.index}_{slot_date}")
                model.AddBoolAnd([has_morning, has_evening]).OnlyEnforceIf(both)
                model.AddBoolOr([has_morning.Not(), has_evening.Not()]).OnlyEnforceIf(both.Not())

                penalties.append(both * PENALTY_FULL_DAY)

    def _count_consecutive_3_day_users(
        self,
        assignments: list[SeniorAssignmentResult],
        context: SeniorContext,
    ) -> int:
        """3 gün üst üste nöbet tutan kullanıcı sayısı"""
        user_dates: dict[str, set[date]] = defaultdict(set)

        for assignment in assignments:
            slot_idx = context.slot_id_to_index.get(assignment.slot_id)
            if slot_idx is not None:
                slot = context.slots[slot_idx]
                user_dates[assignment.user_id].add(slot.date)

        count = 0
        for user_id, dates in user_dates.items():
            sorted_dates = sorted(dates)
            for i in range(len(sorted_dates) - 2):
                d1, d2, d3 = sorted_dates[i], sorted_dates[i + 1], sorted_dates[i + 2]
                if (d2 - d1).days == 1 and (d3 - d2).days == 1:
                    count += 1
                    break

        return count

    def _build_response(
        self,
        result: SeniorSolverResult,
        context: SeniorContext,
        solve_time_ms: float,
    ) -> ScheduleResponse:
        """SolverResult'u ScheduleResponse'a dönüştür"""

        user_assignment_order: dict[str, int] = defaultdict(int)
        safe_limit = context.base_shifts + 1

        assignments = []
        for assignment in result.assignments:
            user_assignment_order[assignment.user_id] += 1
            current_count = user_assignment_order[assignment.user_id]

            is_extra = current_count > safe_limit

            assignments.append(
                Assignment(
                    slotId=assignment.slot_id,
                    seatId=assignment.seat_id,
                    userId=assignment.user_id,
                    seatRole=assignment.seat_role,  # DESK or OPERATOR
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

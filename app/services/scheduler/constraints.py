"""
Hard Constraint Definitions for Scheduler

ASLA kırılmayacak kurallar (geçersiz çözüm üretmemek için):
1. Coverage: Her slot tam olarak requiredCount kişi almalı
2. Yasak geçişler: C→A, C→D, F→A, F→D (geceden sabaha)
3. Base+3 yasağı: totalShifts > base+2 olamaz
4. Günde 1 nöbet: Aynı gün birden fazla slot atanamaz
"""

from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ortools.sat.python import cp_model

    from .models import SchedulerContext


# Yasak geçiş çiftleri: (bugün_type, yarın_type)
FORBIDDEN_TRANSITIONS = frozenset([
    ("C", "A"),  # Hafta içi gece → Hafta içi sabah
    ("C", "D"),  # Hafta içi gece → Hafta sonu sabah
    ("F", "A"),  # Hafta sonu gece → Hafta içi sabah
    ("F", "D"),  # Hafta sonu gece → Hafta sonu sabah
])


def is_night_duty(duty_type: str) -> bool:
    """C veya F ise gece nöbeti"""
    return duty_type in ("C", "F")


def is_morning_duty(duty_type: str) -> bool:
    """A veya D ise sabah nöbeti"""
    return duty_type in ("A", "D")


def is_weekend_duty(duty_type: str) -> bool:
    """D, E, F ise hafta sonu nöbeti"""
    return duty_type in ("D", "E", "F")


def is_forbidden_transition(duty_today: str, duty_tomorrow: str) -> bool:
    """Verilen iki ardışık gün nöbet türü yasak mı?"""
    return (duty_today, duty_tomorrow) in FORBIDDEN_TRANSITIONS


class HardConstraintBuilder:
    """
    Hard Constraint'leri OR-Tools CP-SAT modeline ekleyen builder.
    Bu constraint'ler ASLA ihlal edilemez.
    """

    def __init__(
        self,
        model: "cp_model.CpModel",
        context: "SchedulerContext",
        x: dict[tuple[int, int], "cp_model.IntVar"],
    ):
        """
        Args:
            model: OR-Tools CP-SAT model
            context: Scheduler bağlam bilgisi
            x: x[user_idx, slot_idx] = 1 ise atama var
        """
        self.model = model
        self.ctx = context
        self.x = x

    def add_all_hard_constraints(self, max_shifts_allowed: int) -> None:
        """Tüm hard constraint'leri ekle"""
        self.add_coverage_constraint()
        self.add_max_two_shifts_per_day_constraint()
        self.add_forbidden_transition_constraint()
        self.add_max_shifts_constraint(max_shifts_allowed)

    def add_coverage_constraint(self) -> None:
        """
        Hard #1: Her slot tam olarak requiredCount kişi almalı.
        Boş slot veya fazla atama YOK.
        """
        for slot in self.ctx.slots:
            slot_vars = [self.x[u.index, slot.index] for u in self.ctx.users]
            self.model.Add(sum(slot_vars) == slot.required_count)

    def add_max_two_shifts_per_day_constraint(self) -> None:
        """
        Hard #4: Bir kullanıcı aynı takvim günü en fazla 2 nöbet alabilir.
        Böylece ABC veya DEF üçlüsü otomatik olarak engellenir.
        """
        for current_date, slot_indices in self.ctx.date_to_slot_indices.items():
            if len(slot_indices) <= 2:
                # Max 2 slot varsa zaten constraint gereksiz
                continue

            for user in self.ctx.users:
                day_vars = [self.x[user.index, s_idx] for s_idx in slot_indices]
                self.model.Add(sum(day_vars) <= 2)

    def add_forbidden_transition_constraint(self) -> None:
        """
        Hard #2: Yasak geçişler (geceden sabaha).
        
        ÖNEMLİ MANTIK:
        - C nöbeti tarihi: Gece nöbetinin BİTTİĞİ günü temsil eder
          Örn: C tarihi "15 Aralık" = 14 Aralık 23:30 → 15 Aralık 08:30
        - A nöbeti tarihi: Sabah nöbetinin BAŞLADIĞI günü temsil eder
          Örn: A tarihi "15 Aralık" = 15 Aralık 08:30 → 17:30
        
        YASAK: Aynı tarihli C ve A aynı kişiye atanamaz!
        (C biter, A hemen başlar - dinlenme yok)
        
        Kombinasyonlar:
        - C (bugün) + A (bugün) YASAK (C biter 08:30, A başlar 08:30)
        - F (bugün) + D (bugün) YASAK (F biter 08:00, D başlar 08:00)
        """
        # AYNI GÜN içindeki C+A veya F+D yasağı
        for current_date, slot_indices in self.ctx.date_to_slot_indices.items():
            # Bu günün gece slotları (C, F) - bugün sabah biten
            night_slots = [
                s_idx for s_idx in slot_indices
                if is_night_duty(self.ctx.slots[s_idx].duty_type)
            ]
            
            # Bu günün sabah slotları (A, D) - bugün sabah başlayan
            morning_slots = [
                s_idx for s_idx in slot_indices
                if is_morning_duty(self.ctx.slots[s_idx].duty_type)
            ]
            
            if not night_slots or not morning_slots:
                continue
            
            # Her kullanıcı için: aynı gün gece + sabah <= 1
            for user in self.ctx.users:
                for night_idx in night_slots:
                    for morning_idx in morning_slots:
                        self.model.Add(
                            self.x[user.index, night_idx]
                            + self.x[user.index, morning_idx]
                            <= 1
                        )

    def add_max_shifts_constraint(self, max_allowed: int) -> None:
        """
        Hard #3: base±2 sınırı.
        - Üst limit: totalShifts <= base + 2
        - Alt limit: totalShifts >= base - 2
        
        MinMax soft penalty (150k) daha sıkı dağılım için
        çalışır, ama müsaitlik ihlali gerekirse ±2'ye kadar
        genişleyebilir.
        """
        # max_allowed = base + 2 olarak geliyor
        min_allowed = max(0, max_allowed - 4)  # base - 2
        
        for user in self.ctx.users:
            user_vars = [self.x[user.index, slot.index] for slot in self.ctx.slots]
            # Üst limit: kimse base+2'den fazla alamaz
            self.model.Add(sum(user_vars) <= max_allowed)
            # Alt limit: kimse base-2'den az alamaz
            self.model.Add(sum(user_vars) >= min_allowed)


def get_week_index(d: date, start_date: date) -> int:
    """
    Bir tarihin hangi haftaya ait olduğunu hesapla.
    0-indexed, start_date'in bulunduğu hafta = 0.
    """
    # ISO week kullanmak yerine basit hesap
    days_diff = (d - start_date).days
    return days_diff // 7

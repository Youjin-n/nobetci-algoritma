"""
Internal Domain Models for Scheduler

Scheduler algoritmasının iç işleyişinde kullandığı veri yapıları.
Pydantic schema'larından bağımsız, performans odaklı yapılar.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Literal


@dataclass
class InternalSeat:
    """Bir slot içindeki koltuk"""
    id: str
    index: int  # Slot içi index (0, 1, 2...)
    role: Literal["DESK", "OPERATOR"] | None = None


@dataclass
class InternalUser:
    """Íç kullanım için kullanıcı modeli"""
    id: str
    name: str
    index: int  # OR-Tools için 0-based index

    # Geçmiş istatistikler
    history_total: int = 0
    history_expected: int = 0  # Beklenen toplam (kullanıcının çalıştığı dönemlerin base toplamları)
    history_a: int = 0
    history_b: int = 0
    history_c: int = 0
    history_weekend: int = 0  # D+E+F
    history_night: int = 0  # C+F
    history_desk: int = 0  # A nöbetinde desk sayısı
    history_operator: int = 0  # A nöbetinde operator sayısı

    # Tercihler
    likes_night: bool = False
    dislikes_weekend: bool = False


@dataclass
class InternalSlot:
    """İç kullanım için slot modeli"""
    id: str
    index: int  # OR-Tools için 0-based index
    date: date
    duty_type: Literal["A", "B", "C", "D", "E", "F"]
    day_type: Literal["WEEKDAY", "WEEKEND"]
    required_count: int
    seats: list[InternalSeat] = field(default_factory=list)  # Bu slottaki koltuklar
    difficulty_score: float = 0.0  # Zorluk skoru (unavailability sayısına göre)

    @property
    def is_night(self) -> bool:
        """C veya F ise gece nöbeti"""
        return self.duty_type in ("C", "F")

    @property
    def is_weekend(self) -> bool:
        """D, E, F ise hafta sonu nöbeti"""
        return self.duty_type in ("D", "E", "F")

    @property
    def is_morning(self) -> bool:
        """A veya D ise sabah nöbeti"""
        return self.duty_type in ("A", "D")


@dataclass
class SlotDateInfo:
    """Bir tarihteki slotları gruplama için"""
    date: date
    slot_indices: list[int] = field(default_factory=list)


@dataclass
class SchedulerContext:
    """Scheduler algoritması için tüm bağlam bilgisi"""
    users: list[InternalUser]
    slots: list[InternalSlot]

    # Hızlı lookup için mapping'ler
    user_id_to_index: dict[str, int] = field(default_factory=dict)
    slot_id_to_index: dict[str, int] = field(default_factory=dict)

    # Unavailability set: (user_index, slot_index) çiftleri
    unavailability_set: set[tuple[int, int]] = field(default_factory=set)

    # Tarih bazlı slot grupları
    date_to_slot_indices: dict[date, list[int]] = field(default_factory=dict)

    # Hesaplanan değerler
    total_seats: int = 0  # Toplam doldurulacak koltuk sayısı
    base_shifts: int = 0  # Kişi başı teorik nöbet sayısı

    # Seat tracking
    all_seats: list[InternalSeat] = field(default_factory=list)  # Tüm koltuklar
    seat_id_to_slot_index: dict[str, int] = field(default_factory=dict)  # seat_id -> slot_index

    # Difficulty scoring için
    slot_unavailability_count: dict[int, int] = field(default_factory=dict)

    # Unavailability fairness: "herkes kapattıysa en çok kapatanı yerleştir"
    # Categories: "A", "B", "C", "Weekend" (D+E+F combined)
    # blocked_count_per_category[user_index][category] = bu dönemde bu kullanıcının bu kategoride kaç slot kapattığı
    blocked_count_per_category: dict[int, dict[str, int]] = field(default_factory=dict)
    # max_blocked_per_category[category] = bu kategoride en çok kapatan kullanıcının kaç slot kapattığı
    max_blocked_per_category: dict[str, int] = field(default_factory=dict)

    def get_user_by_index(self, index: int) -> InternalUser:
        return self.users[index]

    def get_slot_by_index(self, index: int) -> InternalSlot:
        return self.slots[index]

    def is_unavailable(self, user_index: int, slot_index: int) -> bool:
        return (user_index, slot_index) in self.unavailability_set


@dataclass
class AssignmentResult:
    """Tek bir atama sonucu"""
    slot_id: str
    seat_id: str  # Koltuk ID
    user_id: str
    seat_role: Literal["DESK", "OPERATOR"] | None = None
    is_extra: bool = False


@dataclass
class SolverResult:
    """Solver'ın döndürdüğü sonuç"""
    assignments: list[AssignmentResult]
    status: str  # OPTIMAL, FEASIBLE, INFEASIBLE, etc.
    solve_time_ms: float
    warnings: list[str] = field(default_factory=list)

    # İstatistikler
    base: int = 0
    max_shifts: int = 0
    min_shifts: int = 0
    users_at_base_plus_2: int = 0
    unavailability_violations: int = 0

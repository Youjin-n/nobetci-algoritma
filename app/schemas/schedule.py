"""
Pydantic v2 Schemas for Schedule API

Bu modül, Next.js frontend ile kontrat görevi gören tüm request/response modellerini içerir.
Frontend formatına uyumlu şekilde güncellenmiştir.
"""

from datetime import date as date_type
from enum import Enum

from pydantic import BaseModel, Field


# --- Enums ---

class DutyType(str, Enum):
    """Nöbet türleri - Hafta içi: A/B/C, Hafta sonu: D/E/F"""
    A = "A"  # 08:00-17:00 (gündüz - desk/operator ayrımı var)
    B = "B"  # 17:00-00:00 (akşam)
    C = "C"  # 00:00-08:00 (gece)
    D = "D"  # Hafta sonu 08:00-17:00
    E = "E"  # Hafta sonu 17:00-00:00
    F = "F"  # Hafta sonu 00:00-08:00 (gece)


class DayType(str, Enum):
    """Gün türü - WEEKDAY veya WEEKEND (tatil günleri de WEEKEND olabilir)"""
    WEEKDAY = "WEEKDAY"
    WEEKEND = "WEEKEND"


class SeatRole(str, Enum):
    """A nöbeti için koltuk rolü"""
    DESK = "DESK"
    OPERATOR = "OPERATOR"


# --- Request Models ---

class Period(BaseModel):
    """Dönem bilgisi"""
    id: str = Field(..., description="Dönem ID")
    name: str = Field(..., description="Dönem adı (örn: '8 Aralık - 4 Ocak 2026')")
    startDate: date_type = Field(..., description="Dönem başlangıç tarihi (YYYY-MM-DD)")
    endDate: date_type = Field(..., description="Dönem bitiş tarihi (YYYY-MM-DD)")


class SlotTypeCounts(BaseModel):
    """Nöbet türü bazında sayılar"""
    A: int = Field(default=0, ge=0)
    B: int = Field(default=0, ge=0)
    C: int = Field(default=0, ge=0)
    D: int = Field(default=0, ge=0)
    E: int = Field(default=0, ge=0)
    F: int = Field(default=0, ge=0)


class UserHistory(BaseModel):
    """Kullanıcının geçmiş nöbet istatistikleri"""
    weekdayCount: int = Field(default=0, ge=0, description="Toplam hafta içi nöbet sayısı")
    weekendCount: int = Field(default=0, ge=0, description="Toplam hafta sonu nöbet sayısı")
    expectedTotal: int | None = Field(default=None, description="Beklenen toplam nöbet sayısı")
    slotTypeCounts: SlotTypeCounts = Field(default_factory=SlotTypeCounts, description="Nöbet türü bazında sayılar")

    @property
    def totalAllTime(self) -> int:
        """Toplam tüm zamanlar (weekday + weekend)"""
        return self.weekdayCount + self.weekendCount

    @property
    def countAAllTime(self) -> int:
        return self.slotTypeCounts.A

    @property
    def countBAllTime(self) -> int:
        return self.slotTypeCounts.B

    @property
    def countCAllTime(self) -> int:
        return self.slotTypeCounts.C

    @property
    def countWeekendAllTime(self) -> int:
        return self.weekendCount

    @property
    def countNightAllTime(self) -> int:
        """Gece nöbetleri (C + F)"""
        return self.slotTypeCounts.C + self.slotTypeCounts.F


class User(BaseModel):
    """Nöbete katılacak kullanıcı"""
    id: str = Field(..., description="Kullanıcı ID")
    name: str = Field(..., description="Kullanıcı adı")
    email: str | None = Field(default=None, description="E-posta (opsiyonel)")
    likesNight: bool = Field(default=False, description="Gece nöbetini sever mi?")
    dislikesWeekend: bool = Field(default=False, description="Hafta sonu nöbetinden kaçınır mı?")
    history: "UserHistory" = Field(default_factory=lambda: UserHistory(), description="Geçmiş istatistikler")


class Seat(BaseModel):
    """Bir slot içindeki koltuk"""
    id: str = Field(..., description="Koltuk ID")
    role: SeatRole | None = Field(default=None, description="A nöbeti için DESK/OPERATOR, diğerleri null")


class Slot(BaseModel):
    """Doldurulması gereken nöbet slotu"""
    id: str = Field(..., description="Slot ID")
    slot_date: date_type = Field(..., alias="date", description="Nöbet tarihi (YYYY-MM-DD)")
    dutyType: DutyType = Field(..., description="Nöbet türü (A/B/C/D/E/F)")
    dayType: DayType = Field(..., description="Gün türü (WEEKDAY/WEEKEND)")
    seats: list[Seat] = Field(..., min_length=1, description="Bu slottaki koltuklar")

    @property
    def requiredCount(self) -> int:
        """Gereken kişi sayısı = koltuk sayısı"""
        return len(self.seats)

    model_config = {"populate_by_name": True}


class Unavailability(BaseModel):
    """Kullanıcı müsait olmama kaydı"""
    userId: str = Field(..., description="Kullanıcı ID")
    slotId: str = Field(..., description="Slot ID")


class ScheduleRequest(BaseModel):
    """Ana request modeli - Next.js'ten gelen JSON"""
    period: Period = Field(..., description="Dönem bilgisi")
    users: list[User] = Field(..., min_length=1, description="Nöbete katılacak kullanıcılar")
    slots: list[Slot] = Field(..., min_length=1, description="Doldurulacak slotlar")
    unavailability: list[Unavailability] = Field(
        default_factory=list, description="Müsait olmama kayıtları"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "period": {
                    "id": "period-1",
                    "name": "8 Aralık - 4 Ocak 2026",
                    "startDate": "2025-12-08",
                    "endDate": "2026-01-04",
                },
                "users": [
                    {
                        "id": "user-1",
                        "name": "Ahmet Furkan Ünnü",
                        "email": "unnu24@itu.edu.tr",
                        "likesNight": False,
                        "dislikesWeekend": True,
                        "history": {
                            "weekdayCount": 12,
                            "weekendCount": 4,
                            "slotTypeCounts": {"A": 3, "B": 5, "C": 2, "D": 4, "E": 1, "F": 1}
                        },
                    }
                ],
                "slots": [
                    {
                        "id": "slot-101",
                        "date": "2025-12-08",
                        "dutyType": "A",
                        "dayType": "WEEKDAY",
                        "seats": [
                            {"id": "seat-1", "role": "DESK"},
                            {"id": "seat-2", "role": "OPERATOR"},
                            {"id": "seat-3", "role": None}
                        ],
                    }
                ],
                "unavailability": [{"userId": "user-1", "slotId": "slot-101"}],
            }
        }
    }


# --- Response Models ---

class Assignment(BaseModel):
    """Tek bir nöbet ataması"""
    slotId: str = Field(..., description="Slot ID")
    seatId: str = Field(..., description="Koltuk ID")
    userId: str = Field(..., description="Atanan kullanıcı ID")
    seatRole: SeatRole | None = Field(
        default=None, description="A nöbeti için koltuk rolü (DESK/OPERATOR)"
    )
    isExtra: bool = Field(
        default=False, description="Bu atama base+2 gibi ekstra bir durum mu?"
    )


class ScheduleMeta(BaseModel):
    """Çözüm meta verileri ve istatistikleri"""
    base: int = Field(..., ge=0, description="Kişi başı teorik temel nöbet sayısı")
    maxShifts: int = Field(..., ge=0, description="En çok nöbet alan kişi kaç nöbet aldı")
    minShifts: int = Field(default=0, ge=0, description="En az nöbet alan kişi kaç nöbet aldı")
    totalSlots: int = Field(default=0, ge=0, description="Toplam slot sayısı")
    totalAssignments: int = Field(default=0, ge=0, description="Toplam atama sayısı")
    usersAtBasePlus2: int = Field(
        default=0, ge=0, description="Base+2'ye ulaşan kullanıcı sayısı"
    )
    unavailabilityViolations: int = Field(
        default=0, ge=0, description="İhlal edilen unavailability sayısı"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Çözüm sırasında oluşan uyarılar"
    )
    solverStatus: str = Field(default="UNKNOWN", description="Solver durumu")
    solveTimeMs: float = Field(default=0.0, ge=0, description="Çözüm süresi (ms)")


class ScheduleResponse(BaseModel):
    """Ana response modeli - Python'dan Next.js'e"""
    assignments: list[Assignment] = Field(..., description="Nöbet atamaları listesi")
    meta: ScheduleMeta = Field(..., description="Çözüm meta verileri")

    model_config = {
        "json_schema_extra": {
            "example": {
                "assignments": [
                    {
                        "slotId": "slot-101",
                        "seatId": "seat-1",
                        "userId": "user-1",
                        "seatRole": "DESK",
                        "isExtra": False,
                    },
                    {
                        "slotId": "slot-101",
                        "seatId": "seat-2",
                        "userId": "user-2",
                        "seatRole": "OPERATOR",
                        "isExtra": False,
                    },
                ],
                "meta": {
                    "base": 8,
                    "maxShifts": 10,
                    "minShifts": 7,
                    "totalSlots": 50,
                    "totalAssignments": 200,
                    "usersAtBasePlus2": 2,
                    "unavailabilityViolations": 1,
                    "warnings": [
                        "Slot slot-105 had to ignore unavailability - all users closed it."
                    ],
                    "solverStatus": "OPTIMAL",
                    "solveTimeMs": 1234.5,
                },
            }
        }
    }

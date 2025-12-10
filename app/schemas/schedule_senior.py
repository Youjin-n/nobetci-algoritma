"""
Pydantic v2 Schemas for Senior Schedule API

Nöbetçi Asistanlar (Senior) için request/response modelleri.
Sadece A nöbetinin sabah/akşam segmentlerini dağıtır.
"""

from datetime import date as date_type
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

# Response modelleri mevcut schedule.py'den import edilecek
from .schedule import Assignment, Period, ScheduleMeta, ScheduleResponse


# --- Enums ---

class Segment(str, Enum):
    """A nöbetinin yarım segmentleri"""
    MORNING = "MORNING"  # Sabah yarısı (örn: 08:30-13:00)
    EVENING = "EVENING"  # Akşam yarısı (örn: 13:00-17:30)


# --- Request Models ---

class SeniorUserHistory(BaseModel):
    """Nöbetçi Asistanın geçmiş nöbet istatistikleri"""
    totalAllTime: int = Field(default=0, ge=0, description="Toplam yarım A sayısı (tüm zamanlar)")
    countAAllTime: int = Field(default=0, ge=0, description="A nöbeti sayısı (tüm zamanlar)")
    # Opsiyonel alanlar (ileride kullanılabilir)
    countMorningAllTime: int = Field(default=0, ge=0, description="Sabah yarısı sayısı (tüm zamanlar)")
    countEveningAllTime: int = Field(default=0, ge=0, description="Akşam yarısı sayısı (tüm zamanlar)")


class SeniorUser(BaseModel):
    """Nöbetçi Asistan kullanıcı"""
    id: str = Field(..., description="Kullanıcı ID")
    name: str = Field(..., description="Kullanıcı adı")
    email: str | None = Field(default=None, description="E-posta (opsiyonel)")
    role: str = Field(default="SENIOR_ASSISTANT", description="Rol (NÖBETÇİ_ASİSTAN veya SENIOR_ASSISTANT)")
    likesMorning: bool = Field(default=False, description="Sabah yarısını tercih eder mi?")
    likesEvening: bool = Field(default=False, description="Akşam yarısını tercih eder mi?")
    history: SeniorUserHistory = Field(
        default_factory=SeniorUserHistory, description="Geçmiş istatistikler"
    )


class SeniorSeat(BaseModel):
    """Senior slot içindeki koltuk"""
    id: str = Field(..., description="Koltuk ID")
    role: Literal["DESK", "OPERATOR"] | None = None  # Senior için genelde null olabilir ama tutarlılık için


class SeniorSlot(BaseModel):
    """A nöbetinin yarım segmenti"""
    id: str = Field(..., description="Slot ID")
    slot_date: date_type = Field(..., alias="date", description="Nöbet tarihi (YYYY-MM-DD)")
    dutyType: Literal["A"] = Field(default="A", description="Nöbet türü (her zaman A)")
    segment: Segment = Field(..., description="Segment (MORNING/EVENING)")
    seats: list[SeniorSeat] = Field(..., min_length=1, description="Bu segmentteki koltuklar")

    @property
    def requiredCount(self) -> int:
        return len(self.seats)

    model_config = {"populate_by_name": True}


class SeniorUnavailability(BaseModel):
    """Nöbetçi Asistan müsait olmama kaydı"""
    userId: str = Field(..., description="Kullanıcı ID")
    slotId: str = Field(..., description="Slot ID")


class SeniorScheduleRequest(BaseModel):
    """
    Nöbetçi Asistan scheduler request modeli.
    
    Sadece A nöbetinin sabah/akşam segmentlerini içerir.
    """
    period: Period = Field(..., description="Dönem bilgisi")
    users: list[SeniorUser] = Field(
        ..., min_length=1, description="Nöbetçi Asistan kullanıcıları"
    )
    slots: list[SeniorSlot] = Field(
        ..., min_length=1, description="Doldurulacak A-MORNING/A-EVENING slotları"
    )
    unavailability: list[SeniorUnavailability] = Field(
        default_factory=list, description="Müsait olmama kayıtları"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "period": {
                    "id": "period-1",
                    "name": "2025 Güz - Dönem 2",
                    "startDate": "2025-12-01",
                    "endDate": "2025-12-31",
                },
                "users": [
                    {
                        "id": "senior-1",
                        "name": "NA Ayşe Kaya",
                        "email": "ayse@example.com",
                        "role": "SENIOR_ASSISTANT",
                        "likesMorning": True,
                        "likesEvening": False,
                        "history": {
                            "totalAllTime": 45,
                            "countAAllTime": 45,
                            "countMorningAllTime": 22,
                            "countEveningAllTime": 23,
                        },
                    }
                ],
                "slots": [
                    {
                        "id": "senior-slot-1",
                        "date": "2025-12-16",
                        "dutyType": "A",
                        "segment": "MORNING",
                        "seats": [{"id": "seat-s1", "role": None}],
                    },
                    {
                        "id": "senior-slot-2",
                        "date": "2025-12-16",
                        "dutyType": "A",
                        "segment": "EVENING",
                        "seats": [{"id": "seat-s2", "role": None}],
                    },
                ],
                "unavailability": [{"userId": "senior-1", "slotId": "senior-slot-2"}],
            }
        }
    }


# Response olarak mevcut ScheduleResponse kullanılacak
# Bu sayede frontend minimal değişiklikle çalışabilir
SeniorScheduleResponse = ScheduleResponse

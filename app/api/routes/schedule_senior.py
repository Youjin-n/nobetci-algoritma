"""
Senior Schedule API Routes

Nöbetçi Asistan nöbet dağıtım endpoint'i.
Sadece A nöbetinin sabah/akşam segmentlerini dağıtır.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.schemas.schedule import ScheduleResponse
from app.schemas.schedule_senior import SeniorScheduleRequest
from app.services.scheduler.senior_solver import SeniorSchedulerSolver

logger = logging.getLogger(__name__)

router = APIRouter()


def get_senior_scheduler(
    settings: Annotated[Settings, Depends(get_settings)],
) -> SeniorSchedulerSolver:
    """Dependency injection için senior scheduler instance"""
    return SeniorSchedulerSolver(settings=settings)


@router.post(
    "/compute-senior",
    response_model=ScheduleResponse,
    summary="Nöbetçi Asistan Nöbet Dağıtımı",
    description="""
    Nöbetçi Asistanlar için A nöbetinin sabah/akşam segmentlerini dağıtır.

    ## Özellikler

    - **Sadece A nöbeti**: Nöbetçi Asistanlar yalnızca A nöbeti tutar
    - **Sabah/Akşam segmentleri**: A nöbeti MORNING ve EVENING olarak ikiye bölünür
    - **Yarım nöbet**: Her segment ayrı bir yarım nöbet olarak sayılır

    ## Kurallar

    ### Hard Constraints (Asla Kırılmaz)
    - Coverage: Her segment requiredCount kadar dolu olmalı
    - Base+3 yasak: Kişi başı max base+2 yarım A nöbeti
    - Günde max 2 segment (sabah + akşam)

    ### Soft Penalties (Ağırlıklandırılmış)
    
    #### Level 1 (100,000) - Çok Ağır
    - Base+2'ye çıkma cezası

    #### Level 2 (10,000 / 7,000) - Ağır
    - Unavailability ihlali: 10,000
    - 3+ gün üst üste yarım A: 7,000 × (runLength - 2)

    #### Level 3 (1,000) - Fairness
    - Yarım A sayısı eşitliği
    - Geçmiş A sayısı ile uzun vadeli denge

    #### Level 4 (100) - Konfor
    - Haftalık yığılma (>2 yarım A/hafta)
    - Aynı gün sabah+akşam alma

    #### Level 5 (10) - Tercihler
    - Sabah/akşam tercihleri (bonus)
    """,
    responses={
        200: {
            "description": "Başarılı nöbet dağıtımı",
            "content": {
                "application/json": {
                    "example": {
                        "assignments": [
                            {"slotId": "senior-slot-1", "userId": "senior-1", "seatRole": None, "isExtra": False},
                            {"slotId": "senior-slot-2", "userId": "senior-2", "seatRole": None, "isExtra": False},
                        ],
                        "meta": {
                            "base": 4,
                            "maxShifts": 5,
                            "minShifts": 4,
                            "totalSlots": 40,
                            "totalAssignments": 40,
                            "usersAtBasePlus2": 0,
                            "unavailabilityViolations": 0,
                            "warnings": [],
                            "solverStatus": "OPTIMAL",
                            "solveTimeMs": 150.5,
                        },
                    }
                }
            },
        },
        422: {"description": "Validation hatası"},
    },
    tags=["Senior Schedule"],
)
async def compute_senior_schedule(
    request: SeniorScheduleRequest,
    scheduler: Annotated[SeniorSchedulerSolver, Depends(get_senior_scheduler)],
) -> ScheduleResponse:
    """
    Nöbetçi Asistanlar için nöbet dağıtımı hesaplar.

    Bu endpoint:
    - Sadece Nöbetçi Asistan rolündeki kullanıcıları kabul eder
    - A nöbetinin sabah (MORNING) ve akşam (EVENING) segmentlerini dağıtır
    - OR-Tools CP-SAT ile optimal çözüm arar
    """
    logger.info(
        f"Computing senior schedule: {len(request.users)} users, "
        f"{len(request.slots)} slots, period={request.period.name}"
    )

    try:
        response = scheduler.solve(request)

        logger.info(
            f"Senior schedule computed: {response.meta.totalAssignments} assignments, "
            f"status={response.meta.solverStatus}, time={response.meta.solveTimeMs:.2f}ms"
        )

        return response

    except Exception as e:
        logger.exception("Error computing senior schedule")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Schedule computation failed: {str(e)}",
        ) from e


@router.get(
    "/health-senior",
    summary="Senior Scheduler Health Check",
    description="Senior scheduler'ın çalışıp çalışmadığını kontrol eder.",
    tags=["Senior Schedule"],
)
async def health_check_senior():
    """Senior scheduler health check endpoint"""
    return {"status": "ok", "service": "senior-scheduler"}

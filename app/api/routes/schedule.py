"""
Schedule API Routes

Nöbet dağıtım endpoint'leri.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.schemas.schedule import ScheduleRequest, ScheduleResponse
from app.services.scheduler import SchedulerSolver

logger = logging.getLogger(__name__)

router = APIRouter()


def get_scheduler(
    settings: Annotated[Settings, Depends(get_settings)],
) -> SchedulerSolver:
    """Dependency injection için scheduler instance"""
    return SchedulerSolver(settings=settings)


@router.post(
    "/compute",
    response_model=ScheduleResponse,
    summary="Nöbet Dağıtımı Hesapla",
    description="""
    Verilen dönem, kullanıcılar, slotlar ve müsaitlik bilgilerine göre
    optimal nöbet dağıtımını hesaplar.

    ## Kurallar

    ### Level 0 (Hard Constraints - Asla Kırılmaz)
    - Yasak ardışık nöbetler: C→A, C→D, F→A, F→D
    - Arka arkaya 3 gün nöbet yasağı
    - base + 3 yasağı

    ### Level 1 (Near-Hard)
    - Müsaitlik (unavailability) saygısı
    - base + 2 sınırı

    ### Level 2-3 (Fairness)
    - A/B/C/Weekend sayılarının eşitlenmesi
    - Gece (C+F) fairness
    - Tarihsel denge

    ### Level 4-5 (Comfort)
    - Haftalık yığılma azaltma
    - Kullanıcı tercihleri
    """,
    responses={
        200: {
            "description": "Başarılı nöbet dağıtımı",
            "content": {
                "application/json": {
                    "example": {
                        "assignments": [
                            {"slotId": "slot-1", "userId": "user-1", "seatRole": "DESK", "isExtra": False}
                        ],
                        "meta": {
                            "base": 8,
                            "maxShifts": 9,
                            "minShifts": 7,
                            "totalSlots": 50,
                            "totalAssignments": 200,
                            "usersAtBasePlus2": 0,
                            "unavailabilityViolations": 0,
                            "warnings": [],
                            "solverStatus": "OPTIMAL",
                            "solveTimeMs": 1234.5
                        }
                    }
                }
            }
        },
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)
async def compute_schedule(
    request: ScheduleRequest,
    scheduler: Annotated[SchedulerSolver, Depends(get_scheduler)],
) -> ScheduleResponse:
    """
    Nöbet dağıtımını hesapla.

    Bu endpoint, Next.js frontend'inden gelen verileri alır ve
    OR-Tools CP-SAT solver kullanarak optimal nöbet ataması üretir.
    """
    try:
        logger.info(
            f"Computing schedule for period '{request.period.name}' "
            f"with {len(request.users)} users and {len(request.slots)} slots"
        )

        response = scheduler.solve(request)

        logger.info(
            f"Schedule computed: {len(response.assignments)} assignments, "
            f"status={response.meta.solverStatus}, time={response.meta.solveTimeMs:.1f}ms"
        )

        return response

    except Exception as e:
        logger.exception("Error computing schedule")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Schedule computation failed: {str(e)}",
        ) from e


@router.get(
    "/health",
    summary="Health Check",
    description="Servisin çalışır durumda olup olmadığını kontrol eder.",
)
async def health_check() -> dict[str, str]:
    """Health check endpoint"""
    return {"status": "healthy", "service": "scheduler"}

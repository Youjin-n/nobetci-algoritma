"""
Core Configuration Module

Uygulama ayarları ve penalty ağırlıkları.
Yeni SPEC'e göre düzenlenmiş ağırlık sistemi.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Uygulama ayarları - .env dosyasından veya environment'tan okunur"""

    # API Ayarları
    app_name: str = "Nöbet Dağıtım Motoru"
    app_version: str = "1.0.0"
    debug: bool = False

    # Scheduler Ayarları
    scheduler_time_limit_seconds: int = 60  # OR-Tools solver zaman limiti
    scheduler_random_seed: int = 42  # Deterministik sonuçlar için seed

    # =========================================================================
    # PENALTY AĞIRLIKLARI (V2 - Güncellenmiş Hiyerarşi)
    # =========================================================================

    # Level 1 – Çok Ağır (Müsaitlik + İdeal sapma + 0 nöbet)
    # Müsaitlik ihlali - EN ağır soft kural
    penalty_unavailability: int = 200_000
    # 0 nöbet kalma cezası - kimse dönem içinde 0 nöbet kalmamalı
    penalty_zero_shifts: int = 80_000
    # ideal_current ± 2 ve ötesi sapma cezaları
    penalty_above_ideal_strong: int = 60_000  # current > ideal+1
    penalty_below_ideal_strong: int = 60_000  # current < ideal-1

    # Level 2 – Ağır (3 gün üst üste)
    # 3 gün üst üste nöbet (runLength >= 3 için, her ekstra gün başına)
    penalty_consecutive_days: int = 7_000

    # Level 3 – Fairness
    # |diff| == 1 için hafif ceza (ideal eşitliğe yaklaştırır)
    penalty_ideal_soft: int = 4_000
    # Tarihsel denge (expectedTotal farkı)
    penalty_history_fairness: int = 3_000
    # Nöbet türü bazında eşitlik (A/B/C/Weekend toplam) - ÇOK GÜÇLÜ
    penalty_fairness_duty_type: int = 50_000
    # Night fairness (C+F toplamı dengesizliği) - ÇOK GÜÇLÜ
    penalty_fairness_night: int = 50_000
    # Weekend slot fairness (D/E/F ayrı ayrı dengeleme) - GÜÇLÜ
    penalty_fairness_weekend_slots: int = 25_000

    # Level 4 – Konfor (hafif)
    # Haftalık yığılma (haftada 2'den fazla nöbet)
    penalty_weekly_clustering: int = 100
    # Arka arkaya gece nöbetleri (C/F ardışık)
    penalty_consecutive_nights: int = 100
    # Aynı gün 2 nöbet tutma (konfor cezası)
    penalty_two_shifts_same_day: int = 100

    # Level 5 – Tercihler (en hafif)
    # dislikesWeekend olan kişiye weekend verme
    penalty_dislikes_weekend: int = 10
    # likesNight olan kişiye night verme (negatif = bonus)
    bonus_likes_night: int = 5

    # Unavailability fairness ve violation tracking
    # "herkes kapattıysa en çok kapatanı yerleştir" tie-breaker
    penalty_unavailability_fairness: int = 1_000
    # Dönem içi her ek unavailability violation için ceza
    # 2. ihlal +25k, 3. ihlal +50k vs. (aynı kişiye abanmayı önler)
    penalty_unavailability_violation: int = 25_000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance döndürür"""
    return Settings()

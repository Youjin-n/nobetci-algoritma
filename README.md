# Nöbet Dağıtım Motoru

FastAPI + OR-Tools CP-SAT ile geliştirilmiş nöbet dağıtım optimizasyon servisi.

## Özellikler

- **OR-Tools CP-SAT Solver**: Google'ın constraint programming çözücüsü
- **Çok Seviyeli Kurallar**: Hard constraint'lerden soft preference'lara
- **Adil Dağıtım**: A/B/C/Weekend/Night fairness
- **Tarihsel Denge**: Geçmiş dönemleri de hesaba katar
- **Pydantic v2**: Modern tip güvenliği ve validasyon

## Kurulum

```bash
# Virtual environment oluştur
python -m venv venv

# Aktive et
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Bağımlılıkları yükle
pip install -r requirements.txt
```

## Çalıştırma

```bash
# Development
uvicorn app.main:app --reload --port 8000

# Production
gunicorn -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000 app.main:app
```

## API Dokümantasyonu

Uygulama çalışırken:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## Ana Endpoint

### POST /schedule/compute

Nöbet dağıtımını hesaplar.

#### Request Body

```json
{
  "period": {
    "id": "periodId",
    "name": "2025 Güz - Dönem 2",
    "startDate": "2025-12-01",
    "endDate": "2025-12-31"
  },
  "users": [
    {
      "id": "userId-1",
      "name": "Ahmet Yılmaz",
      "email": "ahmet@example.com",
      "role": "USER",
      "history": {
        "totalAllTime": 120,
        "countAAllTime": 30,
        "countBAllTime": 30,
        "countCAllTime": 20,
        "countWeekendAllTime": 40,
        "countNightAllTime": 35
      },
      "preferences": {
        "likesNight": true,
        "dislikesWeekend": false
      }
    }
  ],
  "slots": [
    {
      "id": "slotId-101",
      "date": "2025-12-16",
      "dutyType": "A",
      "dayType": "WEEKDAY",
      "requiredCount": 4
    }
  ],
  "unavailability": [{ "userId": "userId-1", "slotId": "slotId-101" }]
}
```

#### Response Body

```json
{
  "assignments": [
    {
      "slotId": "slotId-101",
      "userId": "userId-1",
      "seatRole": "DESK",
      "isExtra": false
    }
  ],
  "meta": {
    "base": 8,
    "maxShifts": 10,
    "minShifts": 7,
    "totalSlots": 50,
    "totalAssignments": 200,
    "usersAtBasePlus2": 2,
    "unavailabilityViolations": 1,
    "warnings": ["..."],
    "solverStatus": "OPTIMAL",
    "solveTimeMs": 1234.5
  }
}
```

## Kurallar

### Level 0 - Hard Constraints (Asla Kırılmaz)

- **Slot Doldurma**: Her slot tam olarak `requiredCount` kişi alır
- **Yasak ardışık nöbetler**: C→A, C→D, F→A, F→D (geceden sabaha)
- **Günde max 2 nöbet**: Aynı gün en fazla 2 nöbet tutulabilir (ABC/DEF üçlüsü imkansız)
- **base+3 yasağı**: Kimse `base+2`'den fazla nöbet alamaz

### Level 1 - Çok Ağır Soft (≈100-200k)

- **Unavailability (200k)**: Müsaitlik kapatmaları mümkün olduğunca saygı görür - EN ağır soft kural
- **ideal±2 sapması (120-140k)**: `ideal_current ±1` serbest, `±2` çok pahalı
- **0 nöbet (80k)**: Kimse bu dönemde 0 nöbet kalmamalı

### Level 2 - Ağır Soft (7k)

- **3 gün üst üste**: Arka arkaya 3+ gün nöbet tutma cezası

### Level 3 - Fairness (~1-3k)

- **Tarihsel denge (3k)**: `expectedTotal` bazlı ince ayar (müsaitlikten daha hafif!)
- **Nöbet türü eşitliği (1k)**: A/B/C/Weekend sayıları arasında denge
- **Gece eşitliği (1k)**: C+F toplam sayısı dengeli dağıtılır

### Level 4 - Konfor (100)

- **Haftalık yığılma**: Haftada 2'den fazla nöbete ceza
- **Aynı gün 2 nöbet**: Mümkünse farklı günlere dağıtılır
- **Ardışık geceler**: İki gün üst üste gece nöbetine ceza

### Level 5 - Tercihler (10/5)

- **Kullanıcı tercihleri**: `likesNight` bonus, `dislikesWeekend` ceza

## Nöbet Türleri

| Tür | Zaman       | Gün Tipi       |
| --- | ----------- | -------------- |
| A   | 08:30-17:30 | WEEKDAY        |
| B   | 17:30-23:30 | WEEKDAY        |
| C   | 23:30-08:30 | WEEKDAY (gece) |
| D   | 08:00-16:00 | WEEKEND        |
| E   | 16:00-23:30 | WEEKEND        |
| F   | 23:20-08:00 | WEEKEND (gece) |

## A Nöbeti Rol Dağılımı

| Kişi Sayısı | Desk | Operator |
| ----------- | ---- | -------- |
| 1           | 0    | 1        |
| 2           | 1    | 1        |
| 3           | 1    | 2        |
| 4           | 2    | 2        |
| 5           | 3    | 2        |
| 6           | 3    | 3        |
| 7           | 4    | 3        |

## Testler

```bash
# Tüm testleri çalıştır
pytest

# Verbose output
pytest -v

# Coverage ile
pytest --cov=app
```

## Proje Yapısı

```
nobetci-v2-algoritma/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       └── schedule.py     # /schedule endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py           # Settings
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── schedule.py         # Pydantic models
│   └── services/
│       ├── __init__.py
│       └── scheduler/
│           ├── __init__.py
│           ├── models.py       # Internal domain models
│           ├── constraints.py  # Hard constraints
│           ├── score.py        # Soft constraints / objectives
│           └── solver.py       # Main solver
├── tests/
│   ├── __init__.py
│   ├── test_scheduler_basic.py
│   └── test_api.py
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Konfigürasyon

Environment değişkenleri veya `.env` dosyası ile yapılandırılabilir:

```env
DEBUG=false
SCHEDULER_TIME_LIMIT_SECONDS=60
SCHEDULER_RANDOM_SEED=42
PENALTY_UNAVAILABILITY_VIOLATION=10000
PENALTY_BASE_PLUS_2=5000
# ... diğer ceza ağırlıkları
```

## Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Build
docker build -t nobetci-scheduler .

# Run
docker run -p 8000:8000 nobetci-scheduler
```

## Lisans

MIT

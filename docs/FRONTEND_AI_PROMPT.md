# Nöbet Dağıtım Motoru - Backend API Documentation

## Overview

This backend provides **TWO SEPARATE scheduling algorithms**:

1. **AÖ (Asistan Öğrenci) Scheduler** - Full shift distribution (A/B/C/D/E/F)
2. **NA (Nöbetçi Asistan) Scheduler** - Half-shift distribution (MORNING/EVENING segments)

**Base URL**: `https://nobeta-a-goritma.onrender.com`

---

# ALGORITHM 1: AÖ (Asistan Öğrenci) Scheduler

**Endpoint**: `POST /schedule/compute`

## AÖ Overview

Distributes **6 different shift types** across weekdays and weekends for research assistants.

## AÖ Duty Types

| Type | Time | Day | Description |
|------|------|-----|-------------|
| **A** | 08:30-17:30 | Weekday | Daytime (DESK/OPERATOR roles) |
| **B** | 17:30-23:30 | Weekday | Evening |
| **C** | 23:30-08:30 | Weekday | **Night** |
| **D** | 08:00-16:00 | Weekend | Morning |
| **E** | 16:00-23:30 | Weekend | Evening |
| **F** | 23:20-08:00 | Weekend | **Night** |

## AÖ Request Schema

```typescript
interface AÖScheduleRequest {
  period: {
    id: string;
    name: string;
    startDate: string;       // "YYYY-MM-DD"
    endDate: string;
  };
  users: AÖUser[];
  slots: AÖSlot[];
  unavailability: Array<{
    userId: string;
    slotId: string;
  }>;
}

interface AÖUser {
  id: string;
  name: string;
  email?: string;
  likesNight: boolean;         // Prefers night shifts (C, F)?
  dislikesWeekend: boolean;    // Avoids weekend shifts (D, E, F)?
  history: {
    totalAllTime: number;      // Total shifts all time
    expectedTotal: number;     // Expected total for fairness
    weekdayCount: number;
    weekendCount: number;
    countAAllTime: number;
    countBAllTime: number;
    countCAllTime: number;
    countNightAllTime: number; // C + F
    countWeekendAllTime: number; // D + E + F
    slotTypeCounts: {
      A: number;
      B: number;
      C: number;
      D: number;
      E: number;
      F: number;
    };
  };
}

interface AÖSlot {
  id: string;
  date: string;                // "YYYY-MM-DD"
  dutyType: "A" | "B" | "C" | "D" | "E" | "F";
  dayType: "WEEKDAY" | "WEEKEND";
  seats: Array<{
    id: string;
    role: "DESK" | "OPERATOR" | null;  // Only for A-shift
  }>;
}
```

## AÖ Response Schema

```typescript
interface AÖScheduleResponse {
  assignments: Array<{
    slotId: string;
    seatId: string;
    userId: string;
    seatRole: "DESK" | "OPERATOR" | null;
    isExtra: boolean;          // True if exceeded base+1
  }>;
  meta: {
    base: number;              // Base shifts per person
    maxShifts: number;
    minShifts: number;
    totalSlots: number;
    totalAssignments: number;
    usersAtBasePlus2: number;
    unavailabilityViolations: number;
    warnings: string[];
    solverStatus: "OPTIMAL" | "FEASIBLE" | "INFEASIBLE";
    solveTimeMs: number;
  };
}
```

## AÖ DESK/OPERATOR Distribution

| People | DESK | OPERATOR |
|--------|------|----------|
| 1 | 0 | 1 |
| 2 | 1 | 1 |
| 3 | 1 | 2 |
| 4 | 2 | 2 |
| 5 | 3 | 2 |
| 6 | 3 | 3 |
| 7 | 4 | 3 |

## AÖ Hard Constraints (Never Violated)

1. **Coverage**: Every seat must be filled
2. **Forbidden transitions**: C→A, C→D, F→A, F→D BANNED (no morning after night)
3. **Max 2 shifts/day**: Same calendar day max 2 shifts
4. **Base+2 limit**: No one gets more than base+2 shifts

## AÖ Soft Penalties

| Level | Rule | Penalty | Description |
|-------|------|---------|-------------|
| **1** | Unavailability violation | 200,000 | Assigning to blocked slot |
| **1** | Unavailability fairness | 1,000 | Tie-breaker when all blocked |
| **1** | Below ideal -2 | 140,000 | Getting too few shifts |
| **1** | Above ideal +2 | 120,000 | Getting too many shifts |
| **1** | Zero shifts | 80,000 | Someone getting 0 shifts |
| **2** | 3+ consecutive days | 7,000 | Shifts on 3+ consecutive days |
| **3** | Ideal ±1 soft | 4,000 | ±1 from ideal shift count |
| **3** | History fairness | 3,000 | Historical balance |
| **3** | Duty type fairness | 1,000 | A/B/C balanced across users |
| **3** | Night fairness | 1,000 | C+F balanced |
| **3** | Weekend slot fairness | 50 | D/E/F individually balanced |
| **4** | Weekly clustering | 100 | >2 shifts per week |
| **4** | Same day 2 shifts | 100 | 2 shifts on same day |
| **4** | Consecutive nights | 100 | Back-to-back C or F |
| **5** | dislikesWeekend | +10 | Weekend hater gets weekend |
| **5** | likesNight | -5 | Night lover gets night (bonus) |

## AÖ Fairness Calculation

```
fark = totalAllTime - expectedTotal
ideal = base - fark
```

**New users start with expectedTotal=0, so they get normal base shifts.**

---

# ALGORITHM 2: NA (Nöbetçi Asistan) Scheduler

**Endpoint**: `POST /schedule/compute-senior`

## NA Overview

Distributes **A-shift HALF segments** for senior assistants. They only work weekday daytime.

## NA Segments

| Segment | Time | Description |
|---------|------|-------------|
| **MORNING** | 08:30-13:00 | Morning half-shift |
| **EVENING** | 13:00-17:30 | Afternoon half-shift |

**NOTE**: NA does NOT have night shifts, weekend shifts, B/C/D/E/F - only A-shift halves.

## NA Request Schema

```typescript
interface NAScheduleRequest {
  period: {
    id: string;
    name: string;
    startDate: string;       // "YYYY-MM-DD"
    endDate: string;
  };
  users: NAUser[];
  slots: NASlot[];
  unavailability: Array<{
    userId: string;
    slotId: string;
  }>;
}

interface NAUser {
  id: string;
  name: string;
  email?: string;
  role: string;                    // "SENIOR_ASSISTANT"
  likesMorning: boolean;           // Prefers morning segment?
  likesEvening: boolean;           // Prefers afternoon segment?
  history: {
    totalAllTime: number;          // Total half-A count
    countAAllTime: number;         // Same as totalAllTime
    countMorningAllTime: number;   // Morning segment count
    countEveningAllTime: number;   // Afternoon segment count
  };
}

interface NASlot {
  id: string;
  date: string;                    // "YYYY-MM-DD"
  dutyType: "A";                   // Always "A"
  segment: "MORNING" | "EVENING";
  seats: Array<{
    id: string;
    role: "DESK" | "OPERATOR" | null;
  }>;
}
```

## NA Response Schema

Same structure as AÖ response. `seatRole` contains "DESK" or "OPERATOR".

## NA DESK/OPERATOR Distribution

| People | DESK | OPERATOR |
|--------|------|----------|
| 1 | 0 | 1 |
| 2 | 1 | 1 |
| 3 | 2 | 1 |

**NOTE**: NA has different DESK/OPERATOR ratio than AÖ!

## NA Hard Constraints (Never Violated)

1. **Coverage**: Every segment seat must be filled
2. **Base+2 limit**: No one gets more than base+2 half-shifts
3. **Max 2 segments/day**: Same day max 2 (morning + afternoon OK)

## NA Soft Penalties

| Level | Rule | Penalty | Description |
|-------|------|---------|-------------|
| **1** | Unavailability violation | 200,000 | Assigning to blocked segment |
| **1** | Above ideal +2 | 120,000 | Too many half-shifts |
| **2** | 3+ consecutive days | 7,000 | Segments on 3+ days in a row |
| **3** | Half-A fairness | 1,000 | Segment count balanced |
| **3** | History fairness | 3,000 | Historical A count balanced |
| **4** | Weekly clustering | 100 | >2 segments per week |
| **4** | Same day both segments | 100 | Full day (morning+evening) |
| **5** | likesMorning | -5 | Morning lover gets morning |
| **5** | likesEvening | -5 | Afternoon lover gets afternoon |

**NOTE**: NA does NOT have likesNight or dislikesWeekend - these don't apply!

---

# Health Check Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /` | API info |
| `GET /schedule/health` | AÖ scheduler health |
| `GET /schedule/health-senior` | NA scheduler health |

---

# Key Differences: AÖ vs NA

| Feature | AÖ | NA |
|---------|----|----|
| **Endpoint** | `/schedule/compute` | `/schedule/compute-senior` |
| **Shift types** | A, B, C, D, E, F | MORNING, EVENING only |
| **Works weekends?** | Yes (D, E, F) | No |
| **Night shifts?** | Yes (C, F) | No |
| **Preferences** | likesNight, dislikesWeekend | likesMorning, likesEvening |
| **DESK/OPERATOR** | 3p = 1D/2O | 3p = 2D/1O |
| **Solver file** | solver.py | senior_solver.py |

---

# Swagger/OpenAPI

- **Swagger UI**: https://nobeta-a-goritma.onrender.com/docs
- **ReDoc**: https://nobeta-a-goritma.onrender.com/redoc

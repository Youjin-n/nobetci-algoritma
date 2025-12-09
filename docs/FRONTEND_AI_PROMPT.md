# Nöbet Dağıtım Motoru - Backend API Documentation

## Overview

This is a **Python FastAPI** backend service that provides optimal shift scheduling using Google OR-Tools CP-SAT constraint solver. The frontend should send scheduling data and receive optimized assignments.

**Base URL**: `https://nobeta-a-goritma.onrender.com`

---

## API Endpoints

### 1. Main Schedule Endpoint

**POST** `/schedule/compute`

Distributes shifts for all duty types (A, B, C for weekdays; D, E, F for weekends).

#### Request Body

```typescript
interface ScheduleRequest {
  period: {
    id: string;              // Unique period ID
    name: string;            // Display name (e.g., "8 Aralık - 4 Ocak 2026")
    startDate: string;       // ISO date "YYYY-MM-DD"
    endDate: string;         // ISO date "YYYY-MM-DD"
  };
  users: User[];             // Array of users to assign shifts
  slots: Slot[];             // Array of shift slots to fill
  unavailability: Array<{    // Users' blocked slots
    userId: string;
    slotId: string;
  }>;
}

interface User {
  id: string;
  name: string;
  email?: string;
  likesNight: boolean;       // Prefers night shifts (C, F)?
  dislikesWeekend: boolean;  // Avoids weekend shifts (D, E, F)?
  history: {
    weekdayCount: number;    // Total historical weekday shifts
    weekendCount: number;    // Total historical weekend shifts
    expectedTotal?: number;  // Expected total (for fairness calculation)
    slotTypeCounts: {
      A: number;             // Historical count per duty type
      B: number;
      C: number;
      D: number;
      E: number;
      F: number;
    };
  };
}

interface Slot {
  id: string;
  date: string;              // ISO date "YYYY-MM-DD"
  dutyType: "A" | "B" | "C" | "D" | "E" | "F";
  dayType: "WEEKDAY" | "WEEKEND";
  seats: Array<{
    id: string;
    role: "DESK" | "OPERATOR" | null;  // Role for A-shift only
  }>;
}
```

#### Response Body

```typescript
interface ScheduleResponse {
  assignments: Array<{
    slotId: string;
    seatId: string;
    userId: string;
    seatRole: "DESK" | "OPERATOR" | null;
    isExtra: boolean;        // True if user exceeded base shifts
  }>;
  meta: {
    base: number;            // Base shifts per person (floor of total/users)
    maxShifts: number;       // Highest shift count among users
    minShifts: number;       // Lowest shift count among users
    totalSlots: number;
    totalAssignments: number;
    usersAtBasePlus2: number; // Users who got base+2 shifts (soft limit)
    unavailabilityViolations: number;  // Forced violations count
    warnings: string[];
    solverStatus: "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | string;
    solveTimeMs: number;
  };
}
```

---

### 2. Senior Schedule Endpoint (Nöbetçi Asistan / NA)

**POST** `/schedule/compute-senior`

Distributes **A-shift segments** for "Nöbetçi Asistan" users. Each day has MORNING (08:30-13:00) and EVENING (13:00-17:30) segments.

#### Segments

| Segment | Time | Description |
|---------|------|-------------|
| **MORNING** | 08:30-13:00 | Morning half-shift |
| **EVENING** | 13:00-17:30 | Afternoon half-shift |

#### Request Body

```typescript
interface SeniorScheduleRequest {
  period: {
    id: string;
    name: string;
    startDate: string;       // "YYYY-MM-DD"
    endDate: string;
  };
  users: SeniorUser[];
  slots: SeniorSlot[];
  unavailability: Array<{
    userId: string;
    slotId: string;
  }>;
}

interface SeniorUser {
  id: string;
  name: string;
  email?: string;
  role: string;                    // "SENIOR_ASSISTANT"
  likesMorning: boolean;           // Prefers morning segment?
  likesEvening: boolean;           // Prefers afternoon segment?
  history: {
    totalAllTime: number;          // Total half-A count (all time)
    countAAllTime: number;         // Same as totalAllTime for seniors
    countMorningAllTime: number;   // Morning segment count
    countEveningAllTime: number;   // Afternoon segment count
  };
}

interface SeniorSlot {
  id: string;
  date: string;                    // "YYYY-MM-DD"
  dutyType: "A";                   // Always "A"
  segment: "MORNING" | "EVENING";  // Which half?
  seats: Array<{
    id: string;
    role: "DESK" | "OPERATOR" | null;  // Can specify role or null
  }>;
}
```

#### NA Algorithm Rules

**Hard Constraints:**
1. Coverage: Every segment filled completely
2. Max base+2 half-shifts per person
3. Max 2 segments per day (morning + afternoon allowed)

**Soft Penalties (Priority Order):**
| Priority | Rule | Penalty |
|----------|------|---------|
| 1 | Unavailability violation | 200,000 |
| 2 | 3+ consecutive days | 7,000 |
| 3 | Fairness (equal distribution) | 1,000-3,000 |
| 4 | Same day both segments | 100 |
| 5 | Preferences (likesMorning/likesEvening) | -5 bonus |

#### DESK/OPERATOR Assignment (NA)

| People | DESK | OPERATOR |
|--------|------|----------|
| 1 | 0 | 1 |
| 2 | 1 | 1 |
| 3 | 2 | 1 |

#### Response

Same `ScheduleResponse` format as main endpoint. `seatRole` contains "DESK" or "OPERATOR".

---

### 3. Health Check Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /` | API info (name, version, docs URL) |
| `GET /schedule/health` | Main scheduler health |
| `GET /schedule/health-senior` | Senior scheduler health |

---

## AÖ (Asistan Öğrenci) Algorithm Rules

### Duty Types

| Type | Time | Day | Description |
|------|------|-----|-------------|
| **A** | 08:30-17:30 | Weekday | Daytime (DESK/OPERATOR roles) |
| **B** | 17:30-23:30 | Weekday | Evening |
| **C** | 23:30-08:30 | Weekday | **Night** |
| **D** | 08:00-16:00 | Weekend | Morning |
| **E** | 16:00-23:30 | Weekend | Evening |
| **F** | 23:20-08:00 | Weekend | **Night** |

### A-Shift DESK/OPERATOR Distribution (AÖ)

| People | DESK | OPERATOR |
|--------|------|----------|
| 1 | 0 | 1 |
| 2 | 1 | 1 |
| 3 | 1 | 2 |
| 4 | 2 | 2 |
| 5 | 3 | 2 |
| 6 | 3 | 3 |
| 7 | 4 | 3 |

### Hard Constraints (Never Violated)

1. **Coverage**: Every seat in every slot must be filled
2. **Forbidden transitions**: No C→A, C→D, F→A, F→D (no morning after night shift)
3. **Max 2 shifts/day**: Same day max 2 shifts (ABC or DEF auto-blocked)
4. **Max shifts**: No one gets more than base+2 shifts (hard limit)

### Soft Penalties (Priority Order)

| Level | Rule | Penalty | Description |
|-------|------|---------|-------------|
| **1** | Unavailability violation | 200,000 | Assigning to blocked slot |
| **1** | Unavailability fairness | 1,000 | Tie-breaker when all blocked |
| **1** | Below ideal -2 | 140,000 | Getting too few shifts |
| **1** | Above ideal +2 | 120,000 | Getting too many shifts |
| **1** | Zero shifts | 80,000 | Someone getting 0 shifts |
| **2** | 3+ consecutive days | 7,000 | Shifts on 3+ consecutive days |
| **3** | Ideal ±1 soft | 4,000 | Light penalty for ±1 from ideal |
| **3** | History fairness | 3,000 | Historical balance (expectedTotal) |
| **3** | Duty type fairness | 1,000 | A/B/C counts balanced across users |
| **3** | Night fairness | 1,000 | C+F (night) counts balanced |
| **3** | Weekend slot fairness | 50 | D/E/F individually balanced |
| **4** | Weekly clustering | 100 | More than 2 shifts per week |
| **4** | Same day 2 shifts | 100 | 2 shifts on same day |
| **4** | Consecutive nights | 100 | Back-to-back night shifts |
| **5** | dislikesWeekend | +10 | Weekend hater gets weekend |
| **5** | likesNight | -5 | Night lover gets night (bonus) |

### Fairness Calculation (expectedTotal)

```
fark = totalAllTime - expectedTotal
ideal = base - fark
```

**Example (Period 4, base=9):**

| User | Total | Expected | Diff | Ideal |
|------|-------|----------|------|-------|
| Ahmet (old) | 29 | 27 | +2 | 7 (less) |
| Ayşe (old) | 25 | 27 | -2 | 11 (more) |
| Mehmet (new) | 0 | 0 | 0 | 9 (normal) |

**New users start fair** - they don't get overloaded.

---

## Example Request (TypeScript/Fetch)

```typescript
const response = await fetch('https://nobeta-a-goritma.onrender.com/schedule/compute', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    period: {
      id: 'p1',
      name: 'Aralık 2025',
      startDate: '2025-12-01',
      endDate: '2025-12-31'
    },
    users: [
      {
        id: 'u1',
        name: 'Ali Yılmaz',
        email: 'ali@example.com',
        likesNight: false,
        dislikesWeekend: true,
        history: {
          weekdayCount: 10,
          weekendCount: 4,
          expectedTotal: 14,
          slotTypeCounts: { A: 3, B: 4, C: 3, D: 2, E: 1, F: 1 }
        }
      }
      // ... more users
    ],
    slots: [
      {
        id: 's1',
        date: '2025-12-01',
        dutyType: 'A',
        dayType: 'WEEKDAY',
        seats: [
          { id: 'seat1', role: 'DESK' },
          { id: 'seat2', role: 'OPERATOR' },
          { id: 'seat3', role: null }
        ]
      }
      // ... more slots
    ],
    unavailability: [
      { userId: 'u1', slotId: 's1' }
    ]
  })
});

const result = await response.json();
// result.assignments -> [{slotId, seatId, userId, seatRole, isExtra}, ...]
// result.meta -> {base, maxShifts, minShifts, solverStatus, ...}
```

---

## Important Notes for Frontend

1. **One slot per (date, dutyType)**: Each date has max 6 slots (A-F for weekdays, D-F for weekends)
2. **Seats determine capacity**: `slot.seats.length` = number of people needed for that slot
3. **History is cumulative**: Include all historical data for fair distribution
4. **Unavailability**: Users can block specific slots; algorithm respects these unless impossible
5. **Response validation**: Check `meta.solverStatus === "OPTIMAL"` for best solution
6. **Weekend/weekday**: Set `dayType` based on actual day type (holidays can be WEEKEND)
7. **Role assignment**: For A-shifts, you can specify DESK/OPERATOR roles on seats

---

## Swagger/OpenAPI Docs

Interactive API documentation available at:
- **Swagger UI**: https://nobeta-a-goritma.onrender.com/docs
- **ReDoc**: https://nobeta-a-goritma.onrender.com/redoc
- **OpenAPI JSON**: https://nobeta-a-goritma.onrender.com/openapi.json

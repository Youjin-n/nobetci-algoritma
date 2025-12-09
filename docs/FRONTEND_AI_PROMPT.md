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

### 2. Senior Schedule Endpoint

**POST** `/schedule/compute-senior`

Distributes **A-shift segments** (MORNING/EVENING) for "Nöbetçi Asistan" users.

#### Request Body

```typescript
interface SeniorScheduleRequest {
  period: {
    id: string;
    name: string;
    startDate: string;
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
  role: string;              // "SENIOR_ASSISTANT" or similar
  likesMorning: boolean;     // Prefers morning segment?
  likesEvening: boolean;     // Prefers evening segment?
  history: {
    totalAllTime: number;    // Total half-A count (all time)
    countAAllTime: number;
    countMorningAllTime: number;
    countEveningAllTime: number;
  };
}

interface SeniorSlot {
  id: string;
  date: string;              // ISO date
  dutyType: "A";             // Always "A" for seniors
  segment: "MORNING" | "EVENING";
  seats: Array<{
    id: string;
    role: null;              // Typically null for seniors
  }>;
}
```

#### Response

Same `ScheduleResponse` format as main endpoint.

---

### 3. Health Check Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /` | API info (name, version, docs URL) |
| `GET /schedule/health` | Main scheduler health |
| `GET /schedule/health-senior` | Senior scheduler health |

---

## Duty Types Explained

| Type | Time | Day |
|------|------|-----|
| **A** | 08:00-17:00 | Weekday (uses DESK/OPERATOR roles) |
| **B** | 17:00-00:00 | Weekday evening |
| **C** | 00:00-08:00 | Weekday **night** |
| **D** | 08:00-17:00 | Weekend morning |
| **E** | 17:00-00:00 | Weekend evening |
| **F** | 00:00-08:00 | Weekend **night** |

---

## Algorithm Rules (Priority Order)

### Hard Constraints (Never Violated)
1. **Coverage**: Every seat in every slot must be filled
2. **Forbidden transitions**: No C→A, C→D, F→A, F→D (no morning after night)
3. **Max consecutive**: No 3+ shifts in consecutive days
4. **Max shifts**: No one gets more than base+2 shifts

### Soft Constraints (Optimized)
| Priority | Rule | Penalty |
|----------|------|---------|
| 1 | Respect unavailability | 200,000 |
| 2 | Keep shifts ≤ base+1 | 60,000-80,000 |
| 3 | Balance A/B/C/Weekend/Night counts | 1,000-3,000 |
| 4 | Avoid weekly clustering | 100 |
| 5 | Honor preferences (likesNight, etc.) | 5-10 |

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

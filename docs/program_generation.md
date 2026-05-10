# Programme Generation - Technical Documentation

This document describes the complete flow for match-programme and schedule generation in Badminton Tournament Planner. It is written for a new agent or developer who needs to understand and continue working on the code.

---

## Overview: Two Separate Steps

Programme generation is divided into two independent steps:

1. **Match programme** - which teams meet each other (rounds, groups, bracket structure). Generated per division. Result: `Match` rows in the database with `match_round`, `match_number`, `team1`, and `team2`.

2. **Time schedule** - when and on which court each match is played. Generated for the whole tournament in one pass. Result: `Match.scheduled_time` and `Match.court` are populated via an optimisation solver.

---

## Data Model (relevant fields)

### `Tournament` (`tournaments/models.py`)
| Field | Type | Meaning |
|------|------|---------|
| `date` | DateField | Tournament date |
| `start_time` | TimeField | Time of the first match |
| `court_count` | IntegerField | Number of available courts |
| `single_match_duration` | IntegerField | Duration in minutes for singles matches |
| `double_match_duration` | IntegerField | Duration in minutes for doubles matches |
| `player_break_time` | IntegerField | Minimum break in minutes between a player's matches |
| `schedule_locked` | BooleanField | Locks the programme against further changes |
| `owner` | FK → User | Which club/user owns the tournament |

### `Division` (`tournaments/models.py`)
| Field | Type | Meaning |
|------|------|---------|
| `discipline` | CharField | `single`, `double`, or `mixed` |
| `tournament_type` | CharField | `group` (pure round-robin), `playoff` (groups + playoff), `tree` (single elimination) |
| `group_count` | IntegerField | Number of groups (playoff only) |
| `advance_count` | IntegerField | Number advancing from each group (playoff only) |
| `teams` | M2M → Team | Registered teams |

### `Match` (`tournaments/models.py`)
| Field | Type | Meaning |
|------|------|---------|
| `division` | FK → Division | Which division the match belongs to |
| `team1` / `team2` | FK → Team | Participating teams. `team1=None` = placeholder (a bracket match that is not ready yet) |
| `match_round` | IntegerField | Round number within the division |
| `match_number` | IntegerField (nullable) | Global running number across the tournament (assigned during match-programme generation) |
| `bracket_slot` | IntegerField (nullable) | Position in the bracket tree (1-based, tree/playoff only) |
| `bracket_label` | CharField (nullable) | Text description for placeholders, for example `Winner of match #5 vs winner of match #6` |
| `phase` | CharField | `group` or `playoff` (only relevant for playoff divisions) |
| `group_number` | IntegerField (nullable) | Group 1, 2, ... (playoff only) |
| `scheduled_time` | DateTimeField (nullable) | Calculated start time (filled by the schedule generator) |
| `court` | CharField (nullable) | Court number as a string (filled by the schedule generator) |
| `status` | CharField | `pending`, `in_progress`, `completed` |
| `walkover` | BooleanField | Walkover match |

---

## Step 1: Match-Programme Generation

**Entry point:** `tournaments/views.py` → `division_generate_schedule(request, pk)`  
**Router:** `tournaments/scheduler.py` → `generate_schedule(division)` (selects the method based on `division.tournament_type`)

### A. Round-robin (`tournament_type = 'group'`)

**Function:** `scheduler.generate_round_robin(division)`

Uses the **circle method** (implemented in `_round_robin_rounds(teams)`):
- Teams are sorted alphabetically by `player1.name`
- One team stays fixed; the others rotate one position per round
- With `n` teams (rounded up to an even number): `n-1` rounds × `n/2` simultaneous matches
- Odd number of teams: a dummy slot is added → the round paired with the dummy becomes a bye round (excluded automatically)

Each match pairing gets `match_round` set to the round number so all matches in the same round can be scheduled simultaneously by the time-schedule generator.

```
Example: 4 teams [A, B, C, D]
Round 1: A-D, B-C
Round 2: A-C, D-B
Round 3: A-B, C-D
```

### B. Single-elimination bracket (`tournament_type = 'tree'`)

**Function:** `scheduler.generate_bracket(division)`

1. Teams are seeded: seeded teams (from `DivisionSeed`) first in seed order, then the rest alphabetically.
2. Bracket size is rounded up to the next power of 2. Extra slots become byes.
3. Placement uses `_seeding_order(n_slots)`, mirroring standard bracketing: seed 1 meets the lowest seed in its half.
4. Round 1: real matches + bye matches (auto-completed with `walkover=True`).
5. Round 2+: placeholder matches with `team1=None, team2=None` and `bracket_label` describing who will meet.
6. Byes are advanced automatically via `_advance_bracket_inline()` so the next round's placeholder gets `team1` filled immediately.
7. When a match is completed, `advance_bracket(match)` calls `_advance_bracket_inline()` to fill the next round.

### C. Playoff (`tournament_type = 'playoff'`)

**Function:** `scheduler.generate_playoff(division)`

Combines round-robin and bracket logic:

1. **Group distribution:** Teams are distributed into `group_count` groups using snake seeding.  
   Team 1→G1, 2→G2, 3→G3, 4→G3, 5→G2, 6→G1, 7→G1, and so on.  
   This ensures an even distribution regardless of the number of teams.

2. **Group stage:** Circle-method round-robin within each group (same as type `group`). Matches get `phase='group'` and `group_number` set.

3. **Playoff bracket:** `advance_count` winner(s) from each group advance. Bracket slots receive labels such as `No.1 grp.1`, `No.2 grp.1`, `No.1 grp.2`, and so on. Placeholders with `phase='playoff'` are created. Bracket round numbers start from `max_group_round + 1`.

### Match Numbering

Immediately after match generation, `division_generate_schedule()` assigns global running numbers (`match_number`) to all new matches, continuing from the highest existing number in the tournament. This ensures unique match references across divisions.

For `tree` divisions, bracket labels are updated after numbering so they reference actual match numbers: `Winner of match #5 vs winner of match #6`.

---

## Step 2: Time-Schedule Generation

**Entry point:** `tournaments/views.py` → `tournament_generate_time_schedule(request, pk)`  
**Implementation:** `tournaments/schedule_planner.py` → `generate_time_schedule(tournament)`

The generator first tries the OR-Tools CP-SAT solver and falls back to a greedy approach on failure:

```python
try:
    return _schedule_ortools(tournament, matches)
except Exception:
    return _schedule_greedy(tournament, matches)
```

Matches considered: all matches with `match_number` set, except byes (`team1!=None, team2=None`).

### Time Indexing

Time is represented as discrete **slots** of `_SLOT_MINUTES = 5` minutes. All durations are rounded up to the nearest slot. A 25-minute match = 5 slots. This reduces the problem size dramatically for the solver.

Conversion back: `start_slot * 5 min + tournament.start_time`.

### OR-Tools CP-SAT Solver (`_schedule_ortools`)

Google OR-Tools CP-SAT is a constraint programming solver that finds the **optimal solution** (shortest overall tournament duration) subject to all hard constraints.

**Variables per match:**
- `s_{id}` — IntVar: start slot (0...horizon)
- `e_{id}` — IntVar: end slot (= s + d, fixed duration)
- `c_{id}_{court}` — BoolVar per court: exactly one court is selected for the match
- Optional interval variables per court for `AddNoOverlap`

**Constraints:**

| Constraint | Implementation |
|-----------|----------------|
| Court capacity: max 1 match per court at a time | `AddNoOverlap(court_intervals[c])` with optional intervals |
| Player conflict: a player cannot play two matches at the same time | `AddNoOverlap` on padded intervals (duration + break) per player |
| Break time: minimum `player_break_time` minutes between a player's matches | The break is included in the player's interval duration (padding) |
| Playoff barrier: playoff matches only after all group matches in the division | `AddMaxEquality` on group end slots + `start >= group_end_max + break` |
| Bracket order: placeholder matches only after both feeder matches | `start[m] >= end[feeder] + break_slots` for both feeders |

**Objective:** Minimise makespan (= the maximum end time across all matches).

**Solver parameters:**
- `max_time_in_seconds = 30.0` — time limit
- `num_workers = 4` — parallelism

**Extracting the solution:** For each match, `solver.value(start_vars[m.id])` is read and converted to a datetime. The court is read by finding the `court_lit` with `value=1`.

### Greedy Fallback (`_schedule_greedy`)

Processes matches in the order `(match_round, division, match_number)` and places each match **greedily**:

1. Compute `player_earliest`: the latest end time + break for all players in the match. A new player uses `start_dt - break_td` as the default (so the first match is not delayed).
2. Find the court that gives the earliest possible start time (given `player_earliest`). On ties, pick the **busiest** court (highest `court_free`) to avoid a delayed match taking up a free court that an earlier match could have used.
3. Update `court_free[idx]` and `player_free[pk]`.

Greedy does not guarantee optimal court utilisation, but it is deterministic and extremely fast.

---

## User Flow

```
Tournament page
    └─► [Generate match programme] per division
            → scheduler.generate_schedule(division)
            → Match rows are created with match_round, match_number
            → Shown in the tournament overview

Schedule page (/tournaments/<pk>/schedule/)
    └─► [⚡ Generate schedule]
            → POST to tournament_generate_time_schedule
            → schedule_planner.generate_time_schedule(tournament)
            → OR-Tools CP-SAT solves the optimisation problem
            → Match.scheduled_time and Match.court are saved
            → Spinner overlay is shown during calculation
            → The page reloads with the finished schedule
    └─► [🔒 Lock programme]
            → tournament.schedule_locked = True
            → Prevents further changes
```

---

## Known Limitations and Possible Improvements

- **Placeholder matches in the schedule:** Match times for bracket finals are estimated from the feeder matches' scheduled end times. When actual results are known, the matches will in practice start at a different time than planned. There is currently no automatic re-scheduling after results are entered.
- **`_SLOT_MINUTES = 5`:** Match durations not divisible by 5 are rounded up. This is acceptable in practice because real matches vary in duration.
- **Solver timeout:** For very large tournaments (100+ matches), `FEASIBLE` (not `OPTIMAL`) may be returned within the time limit. The solution is still valid but not necessarily optimal.
- **Mixed-discipline duration:** `double_match_duration` is used as the fallback for both `double` and `mixed` disciplines. Mixed doubles therefore use the doubles duration.

---

## Key Files

| File | Contents |
|-----|---------|
| `tournaments/scheduler.py` | Match-programme generation: round-robin (circle method), bracket, playoff |
| `tournaments/schedule_planner.py` | Time-schedule generation: OR-Tools CP-SAT solver + greedy fallback |
| `tournaments/models.py` | Tournament, Division, Match, DivisionSeed data models |
| `tournaments/views.py` | `division_generate_schedule`, `tournament_generate_time_schedule` |
| `tournaments/templates/tournaments/schedule.html` | Schedule view with spinner overlay |

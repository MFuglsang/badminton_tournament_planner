# Badminton Tournament Planner - Project Status

**Last updated:** 22 April 2026  
**Tests:** 215 passed · 0 failed · coverage 87%  
**Dev server:** `python manage.py runserver` (running in a separate terminal)

---

## Technical Stack

| Component | Version/details |
|---|---|
| Python | 3.13.9 |
| Django | 6.0.4 |
| Database | SQLite (`db.sqlite3`) |
| Test runner | pytest + pytest-django |
| Virtual environment | `.venv/` |
| Optimisation library | Google OR-Tools 9.15 (CP-SAT solver) |
| Auth | Django built-in (`django.contrib.auth`) |

**Run tests:** `.venv\\Scripts\\python.exe -m pytest players/tests.py tournaments/tests.py -q`  
**Migrations:** `.venv\\Scripts\\python.exe manage.py makemigrations <app> ; manage.py migrate`

---

## Project Structure

```
badminton_tournament_planner/
├── tournament_planner/          # Django project package
│   ├── settings.py              # USE_TZ=True, TIME_ZONE='UTC', LOGIN_URL/REDIRECT
│   ├── urls.py                  # Includes players/, tournaments/, login/logout
│   └── templates/
│       ├── base.html            # Shared layout, nav with user/logout, all CSS
│       ├── base_public.html     # Minimal layout for the login page (no auth nav)
│       └── registration/
│           └── login.html       # Danish login form
├── players/                     # Django app: players and pairs
│   ├── models.py                # Player (owner, rest_until), Team
│   ├── views.py                 # @login_required, owner filtering
│   ├── forms.py                 # TeamForm with owner parameter
│   ├── urls.py                  # Includes player_clear_rest
│   ├── player_status.py         # Player status: playing / resting / available
│   └── templates/players/
├── tournaments/                 # Django app: tournaments, divisions, matches
│   ├── models.py                # Tournament (owner), Division, Match, DivisionSeed
│   ├── views.py                 # @login_required, owner filtering on all views
│   ├── forms.py                 # MatchResultForm with BWF score validation
│   ├── urls.py
│   ├── scheduler.py             # Match-programme generation (circle method + bracket + playoff)
│   ├── schedule_planner.py      # Time schedule: OR-Tools CP-SAT + greedy fallback
│   ├── standings.py             # Standings calculation (round-robin)
│   └── templates/tournaments/
├── program_generation.md        # Technical documentation: match programme + time schedule
├── dockerplan.md                # Production plan: Docker + PostgreSQL + Nginx
├── status.md                    # This document
└── _debug_schedule.py           # Helper script for schedule debugging (can be deleted)
```

---

## Implemented Features

### Multi-user / login
- Django built-in auth with `LOGIN_URL='/login/'`, `LOGIN_REDIRECT_URL='/tournaments/'`, `LOGOUT_REDIRECT_URL='/login/'`
- All views require `@login_required`
- `Tournament` and `Player` have `owner = FK → AUTH_USER_MODEL`
- All querysets filter on `owner=request.user` — data is completely isolated between users
- The nav bar shows the username + Logout button; the Admin link is only visible for `is_staff`
- Danish login form with error message

### Players and pairs
- Create / edit / delete players with name, age, ranking, division, and gender
- Create / edit / delete pairs (singles auto-created via division registration; doubles / mixed created manually)
- `TeamForm.clean()` validates: doubles = same gender, mixed = opposite gender
- Player status: `player_status.py` + `get_busy_info()` calculate who is playing or resting
- **Rest period:** `Player.rest_until` is set automatically after a match. It can be reset manually via the `✕ Rest` button on the player list
- Status badges (🏸 playing, ⏱ resting with countdown) are shown on the schedule and big screen

### Tournaments and divisions
- Create / edit tournaments: name, date, scoring model, court count, singles / doubles duration, break time
- Divisions per tournament with discipline (`single` / `double` / `mixed`) and type (`group` / `playoff` / `tree`)
- Seeding: teams can be assigned seed numbers per division (`DivisionSeed`)
- Programme lock: `schedule_locked` prevents changes to the match programme and time schedule

### Match-programme generation (`scheduler.py`)
See [program_generation.md](program_generation.md) for full documentation.

| Type | Method | Description |
|------|--------|-------------|
| `group` | `generate_round_robin` | Circle method: n-1 rounds × n/2 simultaneous matches |
| `tree` | `generate_bracket` | Single elimination with seeding, byes, and bracket placeholders |
| `playoff` | `generate_playoff` | Group stage (circle method) + playoff bracket |

The circle method ensures that all matches in the same round can be scheduled simultaneously (maximum court utilisation).  
Snake seeding in playoffs distributes teams evenly across groups.

### Time-schedule generation (`schedule_planner.py`)
See [program_generation.md](program_generation.md) for full documentation.

**OR-Tools CP-SAT solver** (primary): Finds the **optimal** solution (shortest tournament duration) by solving a constraint satisfaction problem. Around 30 matches are solved in milliseconds.

**Greedy fallback**: Used if OR-Tools fails. Processes matches one at a time and chooses the earliest available court, with a tie-break in favour of the busiest court.

Both methods respect:
- Court capacity (max 1 match per court at a time)
- Player conflict (a player cannot play two matches simultaneously)
- Break time (minimum `player_break_time` minutes between a player's matches)
- Playoff barrier (playoff matches after all group matches in the division)
- Bracket order (placeholders only after both feeder matches)

### BWF score validation
`MatchResultForm` validates submitted results against BWF rules:
- Format: `"21-15, 18-21, 21-18"` (2 or 3 sets separated by commas)
- Set rules: minimum 21 points to win, deuce at 20-20 (must win by 2), maximum 30-29
- A third set is required only at 1-1 in sets
- The winner field is checked against the set count
- Danish-language validation errors

### Backup / export-import
- `tournament_export`: Downloads a full tournament (players, teams, divisions, matches, seeds) as JSON
- `tournament_import`: Recreates a tournament from a JSON backup — deduplicates players and teams via `get_or_create`
- Export format version 1; an error is shown for unknown versions

### Divisions - extra field
- `Division.schedule_priority` (IntegerField 1-10, default 5): Controls weighting in the OR-Tools optimisation
- Can be set per division via the `division_set_priority` view

### Teams - extra field
- `Team.division` (CharField, optional): Indicates which division the pair plays in (U9-C)

### Public views (no login)
- `/public/` – landing page: choose club and tournament
- `/public/tournament/<pk>/` – standings and match results for a tournament
- `/public/tournament/<pk>/spilleplan/` – read-only schedule with status badges

### UI features
- **Schedule spinner**: Loading overlay with rotating ring during OR-Tools calculation
- **Court numbers**: Not shown in the UI (removed from all templates) but still used internally by scheduling
- **Big-screen view** (`/tournaments/<pk>/bigscreen/`): Shows the next 5 matches with status badges and live rest countdown (JS)
- **Printouts**: Match programme (print-friendly, per division), score sheets (one page per match), player programme (per player without courts)
- **Score sheet**: The oval for the winner name has been removed; the umpire marks it manually
- **Menu item**: The nav bar uses `Pairs` (previously `Teams`)

---

## Data Model

### `players.Player`
| Field | Type | Description |
|---|---|---|
| `name` | CharField | Player name |
| `age` | IntegerField | Age |
| `ranking` | IntegerField | Ranking (lower = better) |
| `division` | CharField (choices) | U9/U11/U13/U15/U17/U19/A/B/C |
| `gender` | CharField (`M`/`K`) | Gender, default `M` |
| `rest_until` | DateTimeField, nullable | Resting until this time (set automatically after a match) |
| `owner` | FK → User, nullable | Club user who owns the player |

### `players.Team`

Note: the application retains the Danish `K` code for female players.
| Field | Type | Description |
|---|---|---|
| `player1` | FK → Player | Always set |
| `player2` | FK → Player, nullable | NULL = singles team |
| `pair_type` | CharField (double/mixed), nullable | NULL for singles |
| `name` | CharField, auto | Auto-set: `Name1 & Name2` or `Name1` |

### `tournaments.Tournament`
| Field | Type | Description |
|---|---|---|
| `name` | CharField | Tournament name |
| `date` | DateField | Date |
| `division_model` | CharField (youth/mixed) | Group model |
| `scoring_model` | CharField | best_of_3_21 / best_of_5_15 |
| `single_match_duration` | IntegerField | Minutes per singles match (default 30) |
| `double_match_duration` | IntegerField | Minutes per doubles match (default 40) |
| `player_break_time` | IntegerField | Minimum player break between matches (default 15) |
| `court_count` | IntegerField | Number of available courts (default 4) |
| `start_time` | TimeField, nullable | Time of the first match |
| `schedule_locked` | BooleanField | Locks further changes |
| `logo` | ImageField, nullable | Shown on printouts |
| `owner` | FK → User, nullable | Club user who owns the tournament |

### `tournaments.Division`
| Field | Type | Description |
|---|---|---|
| `tournament` | FK → Tournament | |
| `name` | CharField | For example `Men's Singles A` |
| `discipline` | CharField (single/double/mixed) | |
| `tournament_type` | CharField (group/playoff/tree) | |
| `group_count` | IntegerField | Number of groups (playoff only) |
| `advance_count` | IntegerField | Teams advancing per group (playoff only) |
| `schedule_priority` | IntegerField (1-10) | Weighting in OR-Tools optimisation (default 5) |
| `teams` | M2M → Team | Registered teams |

### `tournaments.Match`
| Field | Type | Description |
|---|---|---|
| `division` | FK → Division | |
| `team1` / `team2` | FK → Team, nullable | NULL = placeholder or bye |
| `winner` | FK → Team, nullable | Set when completed |
| `score` | CharField, nullable | For example `21-15, 18-21, 21-18` |
| `match_round` | IntegerField | Round number within the division |
| `match_number` | IntegerField, nullable | Global running number across the tournament |
| `bracket_slot` | IntegerField, nullable | Position in the bracket (1-based) |
| `bracket_label` | CharField, nullable | For example `Winner of match #3 vs winner of match #4` |
| `phase` | CharField (group/playoff) | Phase (playoff divisions only) |
| `group_number` | IntegerField, nullable | Group 1, 2, ... (playoff only) |
| `status` | CharField (pending/in_progress/completed) | |
| `walkover` | BooleanField | |
| `scheduled_time` | DateTimeField, nullable | Calculated start time |
| `court` | CharField, nullable | Court number as a string |

---

## URL Overview

### Auth
| URL | Description |
|---|---|
| `/login/` | Login page (Danish form) |
| `/logout/` | POST: log out |

### `players/`
| URL | Name | Description |
|---|---|---|
| `/players/` | `player_list` | Player list with status badges and rest button |
| `/players/add/` | `player_add` | Create player |
| `/players/<pk>/edit/` | `player_edit` | Edit player |
| `/players/<pk>/delete/` | `player_delete` | Delete player |
| `/players/<pk>/clear-rest/` | `player_clear_rest` | POST: reset rest period |
| `/players/teams/` | `team_list` | Pair list |
| `/players/teams/add/` | `team_add` | Create pair |
| `/players/teams/<pk>/edit/` | `team_edit` | Edit pair |
| `/players/teams/<pk>/delete/` | `team_delete` | Delete pair |

### `tournaments/`
| URL | Name | Description |
|---|---|---|
| `/tournaments/` | `tournament_list` | Tournament overview |
| `/tournaments/create/` | `tournament_create` | Create tournament |
| `/tournaments/<pk>/` | `tournament_detail` | Central tournament page |
| `/tournaments/<pk>/edit/` | `tournament_edit` | Edit settings |
| `/tournaments/<pk>/schedule/` | `tournament_schedule` | Time schedule with timestamps |
| `/tournaments/<pk>/schedule/generate/` | `tournament_generate_time_schedule` | POST: run OR-Tools |
| `/tournaments/<pk>/schedule/lock/` | `tournament_toggle_lock` | POST: lock / unlock |
| `/tournaments/<pk>/bigscreen/` | `tournament_bigscreen` | Big-screen view |
| `/tournaments/<pk>/scoresheet/` | `tournament_scoresheet` | Score sheets (all matches) |
| `/tournaments/<pk>/program/print/` | `tournament_program_print` | Match programme (print) |
| `/tournaments/<pk>/division/create/` | `division_create` | POST: create division |
| `/tournaments/division/<pk>/teams/` | `division_update_teams` | POST: update participants |
| `/tournaments/division/<pk>/generate/` | `division_generate_schedule` | POST: generate match programme |
| `/tournaments/division/<pk>/delete/` | `division_delete` | Delete division |
| `/tournaments/division/<pk>/scoresheet/` | `division_scoresheet` | Score sheets for a division |
| `/tournaments/match/<pk>/result/` | `match_record_result` | Record result |
| `/tournaments/match/<pk>/start/` | `match_start` | POST: mark match in progress |
| `/tournaments/match/<pk>/walkover/` | `match_walkover` | Record walkover |

---

## Migrations

### `players/migrations/`
| Migration | Contents |
|---|---|
| 0001-0006 | Basic setup (Player, Team) |
| 0007 | `Player.rest_until` added |
| 0008 | `Player.owner` (FK → User) added |

### `tournaments/migrations/`
| Migration | Contents |
|---|---|
| 0001-0008 | Basic setup, discipline, matches, walkover, match_number, court_count/start_time |
| 0009 | `tournament_type` removed from Tournament, added to Division |
| 0010 | `Match.team2` nullable (bye matches) |
| 0011 | `Match.bracket_label`, `Match.bracket_slot` added; `Match.team1` nullable |
| 0012 | `Match.group_number`, `Match.phase` added |
| 0013 | `Division.group_count`, `Division.advance_count` added |
| 0014 | `Tournament.logo` added |
| 0015 | `Tournament.schedule_locked` added |
| 0016 | `Tournament.owner` (FK → User) added |
| 0017 | `Division.schedule_priority` added |
| 0018 | `Team.division` added |

---

## Known Limitations and Possible Next Steps

- **Re-scheduling after results**: When a bracket placeholder advances (`team1/team2` becomes known), `scheduled_time` is not updated automatically. The user must regenerate the schedule manually.
- **Placeholder times are estimates**: Playoff matches are scheduled based on planned, not actual, end times of feeder matches.
- **Mixed-doubles duration**: Uses `double_match_duration` as the fallback — there is no separate field for mixed.
- **PDF export**: Printouts are handled through browser print; there is no PDF generation.
- **Matches app**: Exists in the project but is empty and unused (can be deleted).
- **`_debug_schedule.py`**: Helper script in the root folder for debugging — should be removed before production.
- **Docker / production**: The plan is documented in [dockerplan.md](dockerplan.md) — awaiting access to Docker.

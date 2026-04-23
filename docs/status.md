# Badminton Tournament Planner – Projektstatus

**Sidst opdateret:** 22. april 2026  
**Tests:** 215 bestået · 0 fejl · dækning 87%  
**Dev-server:** `python manage.py runserver` (kører i separat terminal)

---

## Teknisk stack

| Komponent | Version/detalje |
|---|---|
| Python | 3.13.9 |
| Django | 6.0.4 |
| Database | SQLite (`db.sqlite3`) |
| Test-runner | pytest + pytest-django |
| Virtuel miljø | `.venv/` |
| Optimeringsbibliotek | Google OR-Tools 9.15 (CP-SAT solver) |
| Auth | Django built-in (`django.contrib.auth`) |

**Start tests:** `.venv\Scripts\python.exe -m pytest players/tests.py tournaments/tests.py -q`  
**Migrations:** `.venv\Scripts\python.exe manage.py makemigrations <app> ; manage.py migrate`

---

## Projektstruktur

```
badminton_tournament_planner/
├── tournament_planner/          # Django-projektmappe
│   ├── settings.py              # USE_TZ=True, TIME_ZONE='UTC', LOGIN_URL/REDIRECT
│   ├── urls.py                  # Inkluderer players/, tournaments/, login/logout
│   └── templates/
│       ├── base.html            # Fælles layout, nav med bruger/logout, al CSS
│       ├── base_public.html     # Minimal layout til login-siden (ingen auth-nav)
│       └── registration/
│           └── login.html       # Dansk login-formular
├── players/                     # Django-app: spillere og par
│   ├── models.py                # Player (owner, rest_until), Team
│   ├── views.py                 # @login_required, owner-filtrering
│   ├── forms.py                 # TeamForm med owner-parameter
│   ├── urls.py                  # Inkl. player_clear_rest
│   ├── player_status.py         # Spillerstatus: spiller/hviler/ledig
│   └── templates/players/
├── tournaments/                 # Django-app: turneringer, divisioner, kampe
│   ├── models.py                # Tournament (owner), Division, Match, DivisionSeed
│   ├── views.py                 # @login_required, owner-filtrering på alle views
│   ├── forms.py                 # MatchResultForm med BWF-scorevalidering
│   ├── urls.py
│   ├── scheduler.py             # Kampprogram-generering (cirkel-metode + bracket + playoff)
│   ├── schedule_planner.py      # Spilleplan: OR-Tools CP-SAT + greedy fallback
│   ├── standings.py             # Stillingsberegning (round-robin)
│   └── templates/tournaments/
├── program_generation.md        # Teknisk dokumentation: kampprogram + spilleplan
├── dockerplan.md                # Produktionsplan: Docker + PostgreSQL + Nginx
├── status.md                    # Dette dokument
└── _debug_schedule.py           # Hjælpescript til debugging af tidsplan (kan slettes)
```

---

## Implementerede features

### Multi-bruger / login
- Django built-in auth med `LOGIN_URL='/login/'`, `LOGIN_REDIRECT_URL='/tournaments/'`, `LOGOUT_REDIRECT_URL='/login/'`
- Alle views kræver `@login_required`
- `Tournament` og `Player` har `owner = FK → AUTH_USER_MODEL`
- Alle querysets filtrerer på `owner=request.user` — data er fuldstændig isoleret mellem brugere
- Nav-bar viser brugernavn + Logout-knap; Admin-link kun for `is_staff`
- Dansk login-formular med fejlbesked

### Spillere og par
- Opret/rediger/slet spillere med navn, alder, rangering, division, køn
- Opret/rediger/slet par (singles auto-oprettet via division-tilmelding; double/mixed manuelt)
- `TeamForm.clean()` validerer: double = samme køn, mixed = modsat køn
- Spillerstatus: `player_status.py` + `get_busy_info()` beregner hvem der spiller eller hviler
- **Hvileperiode:** `Player.rest_until` sættes automatisk efter en kamp. Kan nulstilles manuelt via "✕ Hvile"-knap på spillerlisten
- Statusbadges (🏸 spiller, ⏱ hviler med nedtælling) vises på spilleplan og storskærm

### Turneringer og divisioner
- Opret/rediger turnering: navn, dato, scoring-model, baneantal, varighed single/double, pausetid
- Divisioner per turnering med disciplin (`single`/`double`/`mixed`) og type (`group`/`playoff`/`tree`)
- Seeding: hold kan tildeles seed-numre per division (`DivisionSeed`)
- Program-lås: `schedule_locked` forhindrer ændringer af kampprogram og spilleplan

### Kampprogram-generering (scheduler.py)
Se [program_generation.md](program_generation.md) for fuld dokumentation.

| Type | Metode | Beskrivelse |
|------|--------|-------------|
| `group` | `generate_round_robin` | Cirkel-metode: n-1 runder × n/2 simultane kampe |
| `tree` | `generate_bracket` | Enkelt-elimination med seeding, byes og bracket-placeholders |
| `playoff` | `generate_playoff` | Grupperunde (cirkel-metode) + slutspils-bracket |

Cirkel-metoden sikrer at alle kampe i samme runde kan planlægges simultant (maksimal baneudnyttelse).  
Snake-seeding i playoff fordeler hold jævnt på tværs af grupper.

### Spilleplan-generering (schedule_planner.py)
Se [program_generation.md](program_generation.md) for fuld dokumentation.

**OR-Tools CP-SAT solver** (primær): Finder den **optimale** løsning (korteste turneringsvarighed) ved at løse et constraint satisfaction problem. ~30 kampe løses på millisekunder.

**Greedy fallback**: Bruges hvis OR-Tools fejler. Processer kampe en ad gangen, vælger tidligste ledige bane med tiebreak mod den travleste bane.

Begge metoder overholder:
- Banekapacitet (max 1 kamp per bane ad gangen)
- Spillerkonflikt (en spiller kan ikke spille to kampe simultant)
- Pausetid (minimum `player_break_time` minutter mellem en spillers kampe)
- Playoff-barriere (slutspilskampe efter alle gruppekampe i divisionen)
- Bracket-rækkefølge (placeholders tidligst efter begge feeder-kampe)

### BWF score-validering
`MatchResultForm` validerer indsendte resultater mod BWF-regler:
- Format: `"21-15, 18-21, 21-18"` (2 eller 3 sæt adskilt med komma)
- Sæt-regler: min. 21 point for at vinde, deuce ved 20-20 (vindes med 2 points differential), max 30-29
- 3. sæt kræves kun ved 1-1 i sæt
- Winner-felt kontrolleres mod sæt-tællingen
- Dansk-sprogede fejlbeskeder

### Backup / eksport-import
- `tournament_export`: Downloader en hel turnering (spillere, hold, divisioner, kampe, seeds) som JSON
- `tournament_import`: Genopliver en turnering fra JSON-backup — deduplikerer spillere og hold via `get_or_create`
- Eksportformat version 1; fejlmelding ved ukendt version

### Divisioner – ekstra felter
- `Division.schedule_priority` (IntegerField 1–10, default 5): Styrer vægtning i OR-Tools-optimering
- Kan sættes per division via `division_set_priority`-view

### Par – ekstra felt
- `Team.division` (CharField, valgfri): Angiver hvilken række parret spiller i (U9-C)

### Offentlige visninger (ingen login)
- `/public/` – landing: vælg klub og turnering
- `/public/tournament/<pk>/` – stillings- og kampresultater for en turnering
- `/public/tournament/<pk>/spilleplan/` – læse-only spilleplan med statusbadges

### UI-features
- **Spilleplan-spinner**: Loading-overlay med roterende ring under OR-Tools-beregning
- **Bane-numre**: Vises ikke i UI (fjernet fra alle templates) men bruges internt i scheduling
- **Storskærmsvisning** (`/tournaments/<pk>/bigscreen/`): Viser de 5 næste kampe med statusbadges og rest-timer nedtælling i realtid (JS)
- **Udskrifter**: Kampprogram (print-venlig, per division), scoresedler (én side per kamp), spillerprogram (per spiller uden baner)
- **Scoresheet**: Oval til vindernamn er fjernet; dommeren markerer manuelt
- **Menupunkt**: Nav-bar bruger "Par" (tidligere "Hold")

---

## Datamodel

### `players.Player`
| Felt | Type | Beskrivelse |
|---|---|---|
| `name` | CharField | Spillerens navn |
| `age` | IntegerField | Alder |
| `ranking` | IntegerField | Rangering (lavere = bedre) |
| `division` | CharField (choices) | U9/U11/U13/U15/U17/U19/A/B/C |
| `gender` | CharField (M/K) | Køn, default M |
| `rest_until` | DateTimeField, nullable | Hviler indtil dette tidspunkt (sættes automatisk efter kamp) |
| `owner` | FK → User, nullable | Klubbruger der ejer spilleren |

### `players.Team`
| Felt | Type | Beskrivelse |
|---|---|---|
| `player1` | FK → Player | Altid sat |
| `player2` | FK → Player, nullable | NULL = singlespar |
| `pair_type` | CharField (double/mixed), nullable | NULL for singles |
| `name` | CharField, auto | Auto-sat: "Navn1 & Navn2" eller "Navn1" |

### `tournaments.Tournament`
| Felt | Type | Beskrivelse |
|---|---|---|
| `name` | CharField | Turneringens navn |
| `date` | DateField | Dato |
| `division_model` | CharField (youth/mixed) | Gruppemodel |
| `scoring_model` | CharField | best_of_3_21 / best_of_5_15 |
| `single_match_duration` | IntegerField | Minutter pr. singlekamp (default 30) |
| `double_match_duration` | IntegerField | Minutter pr. doublekamp (default 40) |
| `player_break_time` | IntegerField | Min. pause for spiller mellem kampe (default 15) |
| `court_count` | IntegerField | Antal tilgængelige baner (default 4) |
| `start_time` | TimeField, nullable | Tidspunkt for første kamp |
| `schedule_locked` | BooleanField | Låser mod ændringer |
| `logo` | ImageField, nullable | Vises på udskrifter |
| `owner` | FK → User, nullable | Klubbruger der ejer turneringen |

### `tournaments.Division`
| Felt | Type | Beskrivelse |
|---|---|---|
| `tournament` | FK → Tournament | |
| `name` | CharField | Fx "Herresingle A" |
| `discipline` | CharField (single/double/mixed) | |
| `tournament_type` | CharField (group/playoff/tree) | |
| `group_count` | IntegerField | Antal grupper (kun playoff) |
| `advance_count` | IntegerField | Videre per gruppe (kun playoff) |
| `schedule_priority` | IntegerField (1–10) | Vægtning i OR-Tools-optimering (default 5) |
| `teams` | M2M → Team | Tilmeldte hold |

### `tournaments.Match`
| Felt | Type | Beskrivelse |
|---|---|---|
| `division` | FK → Division | |
| `team1` / `team2` | FK → Team, nullable | NULL = placeholder eller bye |
| `winner` | FK → Team, nullable | Sat når afsluttet |
| `score` | CharField, nullable | Fx "21-15, 18-21, 21-18" |
| `match_round` | IntegerField | Rundenummer inden for divisionen |
| `match_number` | IntegerField, nullable | Globalt løbenummer på tværs af turneringen |
| `bracket_slot` | IntegerField, nullable | Position i bracket (1-baseret) |
| `bracket_label` | CharField, nullable | Fx "V-kamp #3 vs V-kamp #4" |
| `phase` | CharField (group/playoff) | Fase (kun playoff-divisioner) |
| `group_number` | IntegerField, nullable | Gruppe 1, 2, … (kun playoff) |
| `status` | CharField (pending/in_progress/completed) | |
| `walkover` | BooleanField | |
| `scheduled_time` | DateTimeField, nullable | Beregnet starttidspunkt |
| `court` | CharField, nullable | Banenummer som streng |

---

## URL-oversigt

### Auth
| URL | Beskrivelse |
|---|---|
| `/login/` | Login-side (dansk formular) |
| `/logout/` | POST: log ud |

### `players/`
| URL | Navn | Beskrivelse |
|---|---|---|
| `/players/` | `player_list` | Spillerliste med statusbadges og hvile-knap |
| `/players/add/` | `player_add` | Opret spiller |
| `/players/<pk>/edit/` | `player_edit` | Rediger spiller |
| `/players/<pk>/delete/` | `player_delete` | Slet spiller |
| `/players/<pk>/clear-rest/` | `player_clear_rest` | POST: nulstil hvileperiode |
| `/players/teams/` | `team_list` | Parliste |
| `/players/teams/add/` | `team_add` | Opret par |
| `/players/teams/<pk>/edit/` | `team_edit` | Rediger par |
| `/players/teams/<pk>/delete/` | `team_delete` | Slet par |

### `tournaments/`
| URL | Navn | Beskrivelse |
|---|---|---|
| `/tournaments/` | `tournament_list` | Turneringsoversigt |
| `/tournaments/create/` | `tournament_create` | Opret turnering |
| `/tournaments/<pk>/` | `tournament_detail` | Central turnerings-side |
| `/tournaments/<pk>/edit/` | `tournament_edit` | Rediger indstillinger |
| `/tournaments/<pk>/schedule/` | `tournament_schedule` | Spilleplan med tidspunkter |
| `/tournaments/<pk>/schedule/generate/` | `tournament_generate_time_schedule` | POST: kør OR-Tools |
| `/tournaments/<pk>/schedule/lock/` | `tournament_toggle_lock` | POST: lås/lås op |
| `/tournaments/<pk>/bigscreen/` | `tournament_bigscreen` | Storskærmsvisning |
| `/tournaments/<pk>/scoresheet/` | `tournament_scoresheet` | Scoresedler (alle kampe) |
| `/tournaments/<pk>/program/print/` | `tournament_program_print` | Kampprogram (udskrift) |
| `/tournaments/<pk>/division/create/` | `division_create` | POST: opret division |
| `/tournaments/division/<pk>/teams/` | `division_update_teams` | POST: opdater deltagere |
| `/tournaments/division/<pk>/generate/` | `division_generate_schedule` | POST: generer kampprogram |
| `/tournaments/division/<pk>/delete/` | `division_delete` | Slet division |
| `/tournaments/division/<pk>/scoresheet/` | `division_scoresheet` | Scoresedler for division |
| `/tournaments/match/<pk>/result/` | `match_record_result` | Registrer resultat |
| `/tournaments/match/<pk>/start/` | `match_start` | POST: sæt kamp i gang |
| `/tournaments/match/<pk>/walkover/` | `match_walkover` | Registrer walk-over |

---

## Migrationer

### `players/migrations/`
| Migration | Indhold |
|---|---|
| 0001–0006 | Basisopsætning (Player, Team) |
| 0007 | `Player.rest_until` tilføjet |
| 0008 | `Player.owner` (FK → User) tilføjet |

### `tournaments/migrations/`
| Migration | Indhold |
|---|---|
| 0001–0008 | Basisopsætning, disciplin, kampe, walkover, match_number, court_count/start_time |
| 0009 | `tournament_type` fjernet fra Tournament, tilføjet til Division |
| 0010 | `Match.team2` nullable (bye-kampe) |
| 0011 | `Match.bracket_label`, `Match.bracket_slot` tilføjet; `Match.team1` nullable |
| 0012 | `Match.group_number`, `Match.phase` tilføjet |
| 0013 | `Division.group_count`, `Division.advance_count` tilføjet |
| 0014 | `Tournament.logo` tilføjet |
| 0015 | `Tournament.schedule_locked` tilføjet |
| 0016 | `Tournament.owner` (FK → User) tilføjet |
| 0017 | `Division.schedule_priority` tilføjet |
| 0018 | `Team.division` tilføjet |

---

## Kendte begrænsninger og mulige næste skridt

- **Re-scheduling efter resultater**: Når en bracket-placeholder avanceres (team1/team2 kendes), opdateres `scheduled_time` ikke automatisk. Bruger skal regenerere spilleplanen manuelt.
- **Placeholder-tider er estimater**: Slutspil-kampe planlægges baseret på planlagte (ikke faktiske) sluttider for feeder-kampe.
- **Mixed double-varighed**: Bruger `double_match_duration` som fallback — der er ikke et separat felt for mixed.
- **PDF-eksport**: Udskrifter foregår via browser-print; ingen PDF-generering.
- **Matches-app**: Eksisterer i projektet men er tom og ubrugt (kan slettes).
- **`_debug_schedule.py`**: Hjælpescript i rod-mappen til debugging — bør slettes inden produktion.
- **Docker / produktion**: Plan er dokumenteret i [dockerplan.md](dockerplan.md) — afventer adgang til Docker.

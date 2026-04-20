# Badminton Tournament Planner – Projektstatus

**Sidst opdateret:** 19. april 2026  
**Tests:** 99 bestået · 0 fejl  
**Dev-server:** `python manage.py runserver` (kører i separat terminal)

---

## Teknisk stack

| Komponent | Version |
|---|---|
| Python | 3.13.9 |
| Django | 6.0.4 |
| Database | SQLite (`db.sqlite3`) |
| Test-runner | pytest + pytest-django |
| Virtuel miljø | `.venv/` |

**Start tests:** `.venv\Scripts\python.exe -m pytest players/tests.py tournaments/tests.py -q`  
**Migrations:** `.venv\Scripts\python.exe manage.py makemigrations <app> ; manage.py migrate`

---

## Projektstruktur

```
badminton_tournament_planner/
├── tournament_planner/          # Django-projektmappe (settings, urls, base.html)
│   ├── settings.py              # USE_TZ=True, TIME_ZONE='UTC'
│   ├── urls.py                  # Inkluderer players/ og tournaments/
│   └── templates/base.html      # Fælles layout, navigation, al CSS (inkl. bracket-CSS)
├── players/                     # Django-app: spillere og par
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   ├── urls.py
│   └── templates/players/
├── tournaments/                 # Django-app: turneringer, divisioner, kampe
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   ├── urls.py
│   ├── scheduler.py             # Kampprogram-generering (round-robin + bracket)
│   ├── schedule_planner.py      # Tidsstyring (bane- og spillerpauser)
│   ├── standings.py             # Stillingsberegning (round-robin)
│   └── templates/tournaments/
└── matches/                     # Tom app (ikke i brug)
```

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

### `players.Team`
Et par (singles eller double/mixed).

| Felt | Type | Beskrivelse |
|---|---|---|
| `player1` | FK → Player | Altid sat |
| `player2` | FK → Player, nullable | NULL = singlespar |
| `pair_type` | CharField (double/mixed), nullable | NULL for singles |
| `name` | CharField, auto | Auto-sat: "Navn1 & Navn2" eller "Navn1" |

**Property:** `is_single` returnerer `True` hvis `player2 is None`.  
**Validering i `TeamForm.clean()`:** double kræver samme køn; mixed kræver modsat køn.

### `tournaments.Tournament`
| Felt | Type | Beskrivelse |
|---|---|---|
| `name` | CharField | Turneringens navn |
| `date` | DateField | Dato |
| `division_model` | CharField (youth/mixed) | Gruppemodel |
| `scoring_model` | CharField (best_of_3_21/best_of_5_15) | Pointmodel |
| `single_match_duration` | IntegerField | Minutter pr. singlekamp (default 30) |
| `double_match_duration` | IntegerField | Minutter pr. doublekamp (default 40) |
| `player_break_time` | IntegerField | Min. pause for spiller mellem kampe (default 15) |
| `court_count` | IntegerField | Antal tilgængelige baner (default 4) |
| `start_time` | TimeField, nullable | Tidspunkt for første kamp |

**Bemærk:** `tournament_type` er fjernet fra `Tournament` – det sættes nu på `Division`.

### `tournaments.Division`
| Felt | Type | Beskrivelse |
|---|---|---|
| `tournament` | FK → Tournament | Tilhørende turnering |
| `name` | CharField | Navn, fx "Herresingle A" |
| `discipline` | CharField (single/double/mixed) | Disciplin |
| `tournament_type` | CharField (group/playoff/tree) | **Type sættes per division** |
| `teams` | M2M → Team | Tilmeldte hold/spillere |

**Disciplin-logik:**
- `single`: Deltagere er individuelle spillere der opslås/oprettes som singles-`Team`
- `double`/`mixed`: Deltagere er eksisterende `Team`-par

### `tournaments.Match`
| Felt | Type | Beskrivelse |
|---|---|---|
| `division` | FK → Division | |
| `team1` | FK → Team, **nullable** | NULL = bracket-placeholder |
| `team2` | FK → Team, **nullable** | NULL = bye eller bracket-placeholder |
| `winner` | FK → Team, nullable | Sat når kamp er afsluttet |
| `score` | CharField, nullable | Fx "21-15, 18-21, 21-18" |
| `match_round` | IntegerField | Runde-nummer (1 = første runde) |
| `match_number` | IntegerField, nullable | Globalt sekventielt nummer på tværs af turnering |
| `bracket_slot` | IntegerField, nullable | Position i bracket (1-indekseret inden for runden) |
| `bracket_label` | CharField, nullable | Fx "V-kamp #3 vs V-kamp #4" – sat på placeholder-kampe |
| `status` | CharField (pending/in_progress/completed) | |
| `walkover` | BooleanField | True = walk-over kamp |
| `scheduled_time` | DateTimeField, nullable | Beregnet starttidspunkt |
| `court` | CharField, nullable | Tildelt bane ("1", "2", ...) |

**Bue-kamp:** `team2=NULL, status='completed', walkover=True, winner=team1, score='Bye'`  
**Placeholder:** `team1=NULL, team2=NULL, bracket_label` sat

---

## URL-oversigt

### `players/`
| URL | Navn | Beskrivelse |
|---|---|---|
| `/players/` | `player_list` | Liste over alle spillere |
| `/players/add/` | `player_add` | Opret spiller |
| `/players/<pk>/edit/` | `player_edit` | Rediger spiller |
| `/players/<pk>/delete/` | `player_delete` | Slet spiller |
| `/players/teams/` | `team_list` | Liste over alle par |
| `/players/teams/add/` | `team_add` | Opret par |
| `/players/teams/<pk>/edit/` | `team_edit` | Rediger par |
| `/players/teams/<pk>/delete/` | `team_delete` | Slet par |

### `tournaments/`
| URL | Navn | Beskrivelse |
|---|---|---|
| `/tournaments/` | `tournament_list` | Oversigt over turneringer |
| `/tournaments/create/` | `tournament_create` | Opret turnering |
| `/tournaments/<pk>/` | `tournament_detail` | Turneringsside (central side) |
| `/tournaments/<pk>/edit/` | `tournament_edit` | Rediger turneringsindstillinger |
| `/tournaments/<pk>/scoresheet/` | `tournament_scoresheet` | Scoresedler (alle kampe) |
| `/tournaments/<pk>/schedule/` | `tournament_schedule` | Spilleplan med tidspunkter |
| `/tournaments/<pk>/schedule/generate/` | `tournament_generate_time_schedule` | POST: beregn tidspunkter |
| `/tournaments/<pk>/division/create/` | `division_create` | POST: opret division |
| `/tournaments/division/<pk>/teams/` | `division_update_teams` | POST: opdater deltagere |
| `/tournaments/division/<pk>/generate/` | `division_generate_schedule` | POST: generer kampprogram |
| `/tournaments/division/<pk>/delete/` | `division_delete` | Slet division |
| `/tournaments/division/<pk>/scoresheet/` | `division_scoresheet` | Scoresedler for division |
| `/tournaments/match/<pk>/result/` | `match_record_result` | Registrer resultat |
| `/tournaments/match/<pk>/start/` | `match_start` | POST: sæt kamp i gang |
| `/tournaments/match/<pk>/walkover/` | `match_walkover` | Registrer walk-over |

---

## Modulbeskrivelser

### `tournaments/scheduler.py`
Indeholder al logik for kampprogram-generering.

**`generate_round_robin(division)`**  
Opretter alle kombinationer (itertools.combinations) af hold. Sletter eksisterende pending-kampe først. Returnerer liste af `Match`-objekter.

**`generate_bracket(division)`**  
Opretter **hele bracket-strukturen på én gang** (alle runder):
1. Sorterer hold efter ranking (lavere = bedre seed).
2. Beregner `bracket_size = 2^ceil(log2(n))`.
3. Placerer hold i slots vha. `_seeding_order()` (standard tennisseeding: seed 1 vs. sidst, 2 vs. næstsidst osv., modsatte sider af bracket).
4. Runde 1: Opretter rigtige kampe. Hold der mangler en modstander → bye-kamp (`team2=None, status='completed'`).
5. Runde 2+: Opretter **placeholder-kampe** (`team1=None, team2=None`) med `bracket_label`.
6. Auto-advancerer bye-vindere til næste runde med `_advance_bracket_inline()`.

**`advance_bracket(match)` / `_advance_bracket_inline(match)`**  
Kaldes efter et resultat gemmes. Finder placeholder-kampen i næste runde (`bracket_slot = ceil(denne_slot/2)`), og udfylder `team1` (ulige slot) eller `team2` (lige slot). Når begge hold kendes, nulstilles `bracket_label`.

**`get_bracket_data(division)`**  
Bygger visualiseringsdata til bracket-diagram. Returnerer `{'rounds': [...], 'total_rounds': int}`. Hvert round-objekt har `label` (Finale/Semifinale/Kvartfinale/...), `slot_height` (px, fordobles per runde), og liste af slots med tilhørende `Match`.

**`get_round_label(round_num, total_rounds)`**  
Beregner dansk rundenavn: 1 fra slut = Finale, 2 fra slut = Semifinale, 3 = Kvartfinale, 4 = Ottendedelsfinale, ellers "Runde N".

**`_seeding_order(n_slots)`**  
Rekursiv funktion der returnerer seed-placeringer. Eks: n=4 → [1,4,2,3] → par (1vs4), (2vs3).

### `tournaments/schedule_planner.py`
Tildeler `scheduled_time` og `court` til alle nummererede kampe i en turnering.

**Algoritme (greedy):**
1. Matches behandles i `match_number`-orden.
2. For **rigtige kampe**: Tidligste start = max(ledigste bane, tidligste spiller-sluttid + pause).
3. For **placeholder-kampe** (bracket, team1=NULL): Tidligste start beregnes fra `bracket_slot_end[(div_id, runde-1, slot)]` for begge feeder-kampe + pause.
4. **Bye-kampe** (team2=NULL) springes over.
5. Bane tildeles greedy: den bane der er ledig tidligst og opfylder spiller-kravet.
6. `bracket_slot_end` opdateres efter hver planlagt kamp, så downstream runder også respekterer tidskrav.

### `tournaments/standings.py`
Beregner stillingen for round-robin divisioner. Konfigureret med `win_points=2, loss_points=0`. Understøtter tiebreakers: head-to-head, derefter net-points. Ignorerer bye-kampe (`team2=None`).

### `tournaments/views.py` – vigtige funktioner

**`tournament_detail`**: Sender for hver division: `standings` (tom liste for tree), `participants_form`, `match_count`, `pending_count`, `bracket_data` (kun for tree).

**`division_generate_schedule`**: 
- Kalder `generate_schedule(division)`.
- Tildeler sekventielle `match_number` på tværs af hele turneringen til **alle** genererede kampe (inkl. placeholders).
- For tree-divisioner: Opdaterer `bracket_label` på placeholders til læsbare tekster som "V-kamp #3 vs V-kamp #4".

**`match_record_result`**: Gemmer resultat, kalder derefter `advance_bracket(match)`.

**`match_walkover`**: Sætter `winner`, `score='21-0, 21-0'`, `walkover=True`, kalder `advance_bracket(match)`.

---

## Templates

### `base.html` (`tournament_planner/templates/`)
- Fælles header med navigation til Spillere, Par, Turneringer.
- Al CSS i én `<style>`-blok (ingen ekstern stylesheet).
- Inkluderer **bracket CSS**: `.bracket-container`, `.bracket-round`, `.bracket-slot`, `.bracket-card`, `.bracket-team`, `.bracket-slot-odd/even` (connector-linjer via `::before`/`::after`).
- Badge-klasser: `.badge-pending`, `.badge-in-progress`, `.badge-completed`, `.badge-walkover`.
- Rang-klasser: `.rank-1`, `.rank-2`, `.rank-3` (til stillingsoversigt).

### `tournament_detail.html`
Hoveddside for en turnering. Sektioner:
1. **Meta-bar**: Dato, scoring, baner, starttid, links til spilleplan og scoresedler.
2. **Opret division**: Inline form med name, discipline, tournament_type.
3. **For hver division** (i `<details>` der kan foldes ud):
   - Deltageroversigt + form til at ændre tilmeldte.
   - **Stilling** (kun group/playoff): Tabel med rangering, kampe, vundet, tabt, point.
   - **Bracket-diagram** (kun tree): Vandret CSS-layout med runder som kolonner. Placeholder-kampe vises i grå kursiv.
   - **Kampprogram-tabel**: Runde, #, Hold 1, Hold 2 (eller `bracket_label` i colspan=2 for placeholders), Resultat, Vinder, Status, Handlinger.
   - Handlingsknapper: ▶ Start, Registrer resultat, WO, Ret resultat. Placeholders viser kun "Afventer spillere".
   - ⚡ Generer kampprogram, 🖨 Scoresedler.

### `schedule.html`
Spilleplanen grupperet efter tidspunkt (Django's `{% regroup %}`). Tre visninger:
- **Afsluttet**: `<details>` med resultat og vinder.
- **I gang**: Aktiv-badge.
- **Kommende (rigtig kamp)**: Hold 1 vs Hold 2.
- **Kommende (placeholder)**: Grå kursiv med `bracket_label`, fx "V-kamp #3 vs V-kamp #4".

### `scoresheet.html`
Printvenlig oversigt over alle kampe. Ekskluderer bye-kampe og placeholder-kampe.

---

## Kampflow (step-by-step)

### Round-robin
1. Opret turnering → Opret division (type: group/playoff, discipline: single/double/mixed).
2. Tilmeld deltagere via "Gem tilmelding".
3. Klik "⚡ Generer kampprogram" → `generate_round_robin()` opretter alle par-kampe, tildeler `match_number`.
4. (Valgfrit) Gå til Spilleplan → "Generer spilleplan" → `generate_time_schedule()` tildeler tidspunkter og baner.
5. Start kampe, registrer resultater → stillingen opdateres automatisk.

### Enkeltelimination (tree)
1. Opret division med type "Enkeltelimination".
2. Tilmeld deltagere.
3. Klik "⚡ Generer kampprogram":
   - Alle runder oprettes med det samme.
   - Runde 1: rigtige kampe (evt. bye-kampe for spillere uden modstander).
   - Runde 2+: placeholder-kampe med tekst som "V-kamp #3 vs V-kamp #4".
   - Alle kampe (inkl. placeholders) tildeles `match_number` og `bracket_label`.
4. (Valgfrit) Generer spilleplan → placeholders placeres i tid baseret på feeder-kampenes estimerede sluttid.
5. Registrer resultater → `advance_bracket()` udfylder automatisk spillerne i næste runde. Når begge kendes, forsvinder `bracket_label` og kampen er klar.

---

## Migrationer (`tournaments/migrations/`)
| Migration | Indhold |
|---|---|
| 0001–0008 | Basisopsætning, disciplin, kampe, walkover, match_number, court_count/start_time, status |
| 0009 | `tournament_type` fjernet fra `Tournament`, tilføjet til `Division` (default 'group') |
| 0010 | `Match.team2` gjort nullable (til bye-kampe) |
| 0011 | `Match.bracket_label`, `Match.bracket_slot` tilføjet; `Match.team1` gjort nullable (til placeholders) |

---

## Hvad mangler / mulige næste skridt

- **Gruppe med slutspil (playoff)**: `tournament_type='playoff'` er defineret men ikke implementeret. Tanken er round-robin i grupper efterfulgt af eliminering for toppen. Pt. behandles det som ren round-robin.
- **Bracket-diagram for placeholders i diagram**: I `bracket_data` / `get_bracket_data()` bruger placeholder-slots `match.bracket_label` til visning – men selve farve/styling i diagram-kortet viser kun "Afventer…". Kan finpudses.
- **Opdatering af spilleplan ved ny kamp**: Når en placeholder-kamp avanceres (team1/team2 udfyldes), opdateres `scheduled_time` ikke automatisk. En bruger må manuelt regenerere spilleplanen.
- **Print-layout**: Spilleplanen og scoresedlerne printer fra browser – ingen PDF-eksport.
- **Brugeradgang / login**: Der er ingen autentificering. Alt er åbent.
- **Matches-app**: Eksisterer i projektet men er tom og ubrugt.

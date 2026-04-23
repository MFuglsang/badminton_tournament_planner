# Programgenerering – teknisk dokumentation

Dette dokument beskriver det komplette flow for kampprogram- og spilleplansgenerering i badminton tournament planner. Det er skrevet til brug for en ny agent eller udvikler der skal forstå og arbejde videre med koden.

---

## Oversigt: to separate trin

Programgenereringen er opdelt i to uafhængige trin:

1. **Kampprogram** – hvilke hold møder hinanden (runder, grupper, bracket-struktur). Genereres per division. Resultat: `Match`-rækker i databasen med `match_round`, `match_number`, `team1`, `team2`.

2. **Spilleplan** – hvornår og på hvilken bane hver kamp afvikles. Genereres for hele turneringen på én gang. Resultat: `Match.scheduled_time` og `Match.court` udfyldes via en optimeringssolver.

---

## Datamodel (relevante felter)

### `Tournament` (tournaments/models.py)
| Felt | Type | Betydning |
|------|------|-----------|
| `date` | DateField | Turneringsdato |
| `start_time` | TimeField | Klokkeslæt for første kamp |
| `court_count` | IntegerField | Antal tilgængelige baner |
| `single_match_duration` | IntegerField | Varighed i minutter for singlekampe |
| `double_match_duration` | IntegerField | Varighed i minutter for doublekampe |
| `player_break_time` | IntegerField | Minimumspause i minutter mellem en spillers kampe |
| `schedule_locked` | BooleanField | Låser programmet mod ændringer |
| `owner` | FK → User | Hvilken klub/bruger der ejer turneringen |

### `Division` (tournaments/models.py)
| Felt | Type | Betydning |
|------|------|-----------|
| `discipline` | CharField | `single`, `double` eller `mixed` |
| `tournament_type` | CharField | `group` (ren round-robin), `playoff` (grupper + slutspil), `tree` (enkelt-elimination) |
| `group_count` | IntegerField | Antal grupper (kun playoff) |
| `advance_count` | IntegerField | Antal der går videre per gruppe (kun playoff) |
| `teams` | M2M → Team | Tilmeldte hold |

### `Match` (tournaments/models.py)
| Felt | Type | Betydning |
|------|------|-----------|
| `division` | FK → Division | Hvilken division kampen tilhører |
| `team1` / `team2` | FK → Team | Deltagende hold. `team1=None` = placeholder (bracket-kamp der ikke er klar endnu) |
| `match_round` | IntegerField | Rundenummer inden for divisionen |
| `match_number` | IntegerField (nullable) | Globalt løbenummer på tværs af turneringen (tildeles ved kampprogram-generering) |
| `bracket_slot` | IntegerField (nullable) | Position i bracket-træet (1-baseret, kun tree/playoff) |
| `bracket_label` | CharField (nullable) | Tekstbeskrivelse til placeholders, f.eks. "V-kamp #5 vs V-kamp #6" |
| `phase` | CharField | `group` eller `playoff` (kun relevant for playoff-divisioner) |
| `group_number` | IntegerField (nullable) | Gruppe 1, 2, … (kun playoff) |
| `scheduled_time` | DateTimeField (nullable) | Beregnet starttidspunkt (udfyldes af spilleplansgeneratoren) |
| `court` | CharField (nullable) | Banenummer som streng (udfyldes af spilleplansgeneratoren) |
| `status` | CharField | `pending`, `in_progress`, `completed` |
| `walkover` | BooleanField | Walk-over-kamp |

---

## Trin 1: Kampprogram-generering

**Entry point:** `tournaments/views.py` → `division_generate_schedule(request, pk)`  
**Router:** `tournaments/scheduler.py` → `generate_schedule(division)` (vælger metode ud fra `division.tournament_type`)

### A. Round-robin (`tournament_type = 'group'`)

**Funktion:** `scheduler.generate_round_robin(division)`

Bruger **cirkel-metoden** (implementeret i `_round_robin_rounds(teams)`):
- Hold sorteres alfabetisk efter player1.name
- Ét hold holdes fast; de øvrige roterer én plads per runde
- Med `n` hold (afrundet op til lige tal): `n-1` runder × `n/2` samtidige kampe
- Ulige antal hold: en dummy-plads tilføjes → den runde der har dummy som modstander er en fridag (ekskluderes automatisk)

Hvert kamp-par får `match_round` sat til rundenummeret, så alle kampe i samme runde kan planlægges simultant af spilleplansgeneratoren.

```
Eksempel: 4 hold [A, B, C, D]
Runde 1: A-D, B-C
Runde 2: A-C, D-B
Runde 3: A-B, C-D
```

### B. Enkelt-elimination bracket (`tournament_type = 'tree'`)

**Funktion:** `scheduler.generate_bracket(division)`

1. Hold seedes: seedede hold (fra `DivisionSeed`) først i seed-rækkefølge, derefter resten alfabetisk.
2. Bracket-størrelse rundes op til næste potens af 2. Overskydende pladser = byes.
3. Placering via `_seeding_order(n_slots)` der afspejler standard bracketing: seed 1 møder laveste seed i sin halvdel.
4. Runde 1: reelle kampe + bye-kampe (auto-completed med `walkover=True`).
5. Runde 2+: placeholder-kampe med `team1=None, team2=None` og `bracket_label` der beskriver hvem der mødes.
6. Byes avanceres automatisk via `_advance_bracket_inline()` så næste rundes placeholder straks får `team1` udfyldt.
7. Når en kamp gennemføres kalder `advance_bracket(match)` → `_advance_bracket_inline()` for at udfylde næste runde.

### C. Playoff (`tournament_type = 'playoff'`)

**Funktion:** `scheduler.generate_playoff(division)`

Kombinerer round-robin og bracket:

1. **Fordeling i grupper:** Hold fordeles i `group_count` grupper via snake-seeding:  
   Hold 1→G1, 2→G2, 3→G3, 4→G3, 5→G2, 6→G1, 7→G1, osv.  
   Dette sikrer jævn fordeling uanset antal hold.

2. **Gruppespil:** Cirkel-metode round-robin per gruppe (samme som type `group`). Kampe får `phase='group'` og `group_number` sat.

3. **Slutspil-bracket:** `advance_count` vinder(e) per gruppe går videre. Bracket-pladser tildeles labels som "Nr.1 gr.1", "Nr.2 gr.1", "Nr.1 gr.2" osv. Placeholders med `phase='playoff'` oprettes. Bracket-rundenumre starter fra `max_group_round + 1`.

### Match-nummerering

Umiddelbart efter kamp-generering tildeler `division_generate_schedule()` globale løbenumre (`match_number`) til alle nye kampe, der fortsætter fra det højeste eksisterende nummer i turneringen. Dette sikrer entydige kampreferencer på tværs af divisioner.

For `tree`-divisioner opdateres bracket-labels efter nummerering, så de refererer til faktiske kampnumre: "V-kamp #5 vs V-kamp #6".

---

## Trin 2: Spilleplan-generering

**Entry point:** `tournaments/views.py` → `tournament_generate_time_schedule(request, pk)`  
**Implementering:** `tournaments/schedule_planner.py` → `generate_time_schedule(tournament)`

Generatoren forsøger OR-Tools CP-SAT solveren og falder tilbage til greedy ved fejl:

```python
try:
    return _schedule_ortools(tournament, matches)
except Exception:
    return _schedule_greedy(tournament, matches)
```

Kampe der behandles: alle kampe med `match_number` sat, bortset fra byes (`team1!=None, team2=None`).

### Tidsindeksering

Tid repræsenteres som diskrete **slots** af `_SLOT_MINUTES = 5` minutter. Alle varigheder rundes op til nærmeste slot. En 25-min kamp = 5 slots. Dette reducerer problemstørrelsen drastisk for solveren.

Konvertering tilbage: `start_slot * 5 min + tournament.start_time`.

### OR-Tools CP-SAT solver (`_schedule_ortools`)

Google OR-Tools CP-SAT er en Constraint Programming solver der finder den **optimale løsning** (korteste samlede turneringsvarighed) givet alle hårde krav.

**Variabler per kamp:**
- `s_{id}` — IntVar: startslot (0…horizon)
- `e_{id}` — IntVar: slutslot (= s + d, fast duration)
- `c_{id}_{court}` — BoolVar per bane: exactly-one (kampen er på præcis én bane)
- Optional interval-variabler per bane til `AddNoOverlap`

**Constraints:**

| Constraint | Implementering |
|-----------|----------------|
| Banekapacitet: max 1 kamp per bane ad gangen | `AddNoOverlap(court_intervals[c])` med optionelle intervaller |
| Spillerkonflikt: en spiller kan ikke spille to kampe på samme tid | `AddNoOverlap` på padded intervals (varighed + break) per spiller |
| Pausetid: minimum `player_break_time` min mellem en spillers kampe | Pause inkluderes i spillerens interval-varighed (padding) |
| Playoff-barriere: slutspilskampe tidligst efter alle gruppekampe i divisionen | `AddMaxEquality` på gruppe-slutslots + `start >= group_end_max + break` |
| Bracket-rækkefølge: placeholder-kampe tidligst efter begge feeder-kampe | `start[m] >= end[feeder] + break_slots` for begge feedere |

**Objektiv:** Minimér makespan (= max end-tid for alle kampe).

**Solver-parametre:**
- `max_time_in_seconds = 30.0` — tidsgrænse
- `num_workers = 4` — parallelisering

**Løsningsudtræk:** For hvert match aflæses `solver.value(start_vars[m.id])` → konverteres til datetime. Bane aflæses ved at finde den `court_lit` der har value=1.

### Greedy fallback (`_schedule_greedy`)

Behandler kampe i rækkefølgen `(match_round, division, match_number)` og placerer hver kamp **grådigt**:

1. Beregn `player_earliest`: seneste sluttidspunkt + break for alle spillere i kampen. Ny spiller bruger `start_dt - break_td` som default (så første kamp ikke forskydes).
2. Find den bane der giver tidligst mulig starttid (givet `player_earliest`). Ved uafgjort vælges den **travleste** bane (højest `court_free`) for at undgå at en forsinket kamp optager en fri bane som en tidligere kamp godt kunne bruge.
3. Opdatér `court_free[idx]` og `player_free[pk]`.

Greedy garanterer ikke optimal baneudnyttelse, men er deterministisk og lynhurtig.

---

## Brugerflow

```
Turneringsside
    └─► [Generer kampprogram] per division
            → scheduler.generate_schedule(division)
            → Match-rækker oprettes med match_round, match_number
            → Vises i turneringsoversigten

Spilleplanside (/tournaments/<pk>/schedule/)
    └─► [⚡ Generer spilleplan]
            → POST til tournament_generate_time_schedule
            → schedule_planner.generate_time_schedule(tournament)
            → OR-Tools CP-SAT løser optimeringsproblemet
            → Match.scheduled_time og Match.court gemmes
            → Spinner-overlay vises under beregning
            → Siden genindlæser med den færdige spilleplan
    └─► [🔒 Lås program]
            → tournament.schedule_locked = True
            → Forhindrer yderligere ændringer
```

---

## Kendte begrænsninger og mulige forbedringer

- **Placeholder-kampe i spilleplanen:** Kamp-tid for bracket-finaler estimeres ud fra feeder-matchenes planlagte sluttider. Når de faktiske resultater kendes vil kampene i praksis starte til en anden tid end planlagt. Der er pt. ingen automatisk re-scheduling efter resultater.
- **`_SLOT_MINUTES = 5`:** Kampvarigheder der ikke er delelige med 5 rundes op. Dette er acceptabelt i praksis da reelle kampe varierer i varighed.
- **Solver-timeout:** Ved meget store turneringer (100+ kampe) kan `FEASIBLE` (ikke `OPTIMAL`) returneres inden for tidsgrænsen. Løsningen er stadig gyldig men ikke nødvendigvis optimal.
- **Mix af discipliner:** `double_match_duration` bruges som fallback for både `double` og `mixed` discipline. Mixed double bruger altså double-varighed.

---

## Nøglefiler

| Fil | Indhold |
|-----|---------|
| `tournaments/scheduler.py` | Kampprogram-generering: round-robin (cirkel-metode), bracket, playoff |
| `tournaments/schedule_planner.py` | Spilleplan-generering: OR-Tools CP-SAT solver + greedy fallback |
| `tournaments/models.py` | Tournament, Division, Match, DivisionSeed datamodeller |
| `tournaments/views.py` | `division_generate_schedule`, `tournament_generate_time_schedule` |
| `tournaments/templates/tournaments/schedule.html` | Spilleplan-visning med spinner-overlay |

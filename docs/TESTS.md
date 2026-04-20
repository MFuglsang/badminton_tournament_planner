# Test Vejledning

## Oversigt
Projektet bruger **pytest** og **pytest-django** til afvikling af tests, samt **coverage** til måling af testdækning. Alle tests befinder sig i `tests.py` i de respektive apps.

---

## Krav
Sørg for at dependencies er installeret:
```bash
pip install -r requirements.txt
```

---

## Afvikling af tests

### Kør alle tests
```bash
c:/github/badminton_tournament_planner/.venv/Scripts/pytest.exe
```

### Kør tests med detaljeret output
```bash
c:/github/badminton_tournament_planner/.venv/Scripts/pytest.exe -v
```

### Kør tests for en specifik app
```bash
c:/github/badminton_tournament_planner/.venv/Scripts/pytest.exe players/
c:/github/badminton_tournament_planner/.venv/Scripts/pytest.exe tournaments/
```

### Kør en specifik test-klasse eller test
```bash
# Kør én klasse
c:/github/badminton_tournament_planner/.venv/Scripts/pytest.exe tournaments/tests.py::RoundRobinSchedulerTest

# Kør én test
c:/github/badminton_tournament_planner/.venv/Scripts/pytest.exe tournaments/tests.py::RoundRobinSchedulerTest::test_generates_correct_number_of_matches
```

---

## Coverage

### Kør tests med coverage-måling
```bash
c:/github/badminton_tournament_planner/.venv/Scripts/coverage.exe run -m pytest
```

### Vis coverage rapport i terminalen
```bash
c:/github/badminton_tournament_planner/.venv/Scripts/coverage.exe report
```

### Generer HTML-rapport (åbn `htmlcov/index.html` i browseren)
```bash
c:/github/badminton_tournament_planner/.venv/Scripts/coverage.exe html
start htmlcov/index.html
```

Coverage-konfigurationen findes i `.coveragerc` i projektets rodmappe.

---

## Teststruktur

### `players/tests.py`
| Klasse | Hvad testes |
|--------|-------------|
| `PlayerModelTest` | `__str__`, gyldige divisions-valg |
| `TeamModelTest` | Auto-navn, brugerdefineret navn, `__str__` |
| `PlayerViewTest` | Liste, tilføj (GET/POST), rediger (GET/POST/404) |
| `TeamViewTest` | Liste, tilføj (GET/POST), rediger (GET/404) |

### `tournaments/tests.py`
| Klasse | Hvad testes |
|--------|-------------|
| `TournamentModelTest` | `__str__`, alle turneringstyper |
| `DivisionModelTest` | `__str__`, tilføjelse af hold |
| `MatchModelTest` | `__str__`, default status |
| `RoundRobinSchedulerTest` | Antal kampe, status, regenerering, tom division |
| `BracketSchedulerTest` | Antal kampe i runde 1, round-nummer, tom division |
| `GenerateScheduleRouterTest` | Korrekt scheduler vælges per turneringstype |
| `TournamentViewTest` | Liste, detalje, 404, generer kampprogram |
| `MatchResultViewTest` | GET, POST (gyldigt/ugyldigt), 404 |

---

## Nuværende Coverage (seneste kørsel)

| Modul | Coverage |
|-------|----------|
| `players/models.py` | 100% |
| `players/forms.py` | 100% |
| `players/views.py` | 91% |
| `tournaments/models.py` | 100% |
| `tournaments/forms.py` | 100% |
| `tournaments/views.py` | 100% |
| `tournaments/scheduler.py` | 100% |
| **Total** | **97%** |

---

## Konventioner for nye tests

- **Placering**: `tests.py` i den relevante app-mappe.
- **Navngivning**: Klasser starter med `Test`, metoder starter med `test_`.
- **Helper-funktioner**: Brug `make_*` hjælpefunktioner øverst i filen til at oprette testdata.
- **Dæk altid**: Model `__str__`, view GET/POST, 404-håndtering, og forretningslogik (f.eks. scheduler).
- **Isolering**: Brug `TestCase` — databasen nulstilles automatisk mellem tests.

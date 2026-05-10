# Test Guide

## Overview
The project uses **pytest** and **pytest-django** to run tests, and **coverage** to measure test coverage. All tests live in `tests.py` within the relevant apps.

---

## Requirements
Make sure the dependencies are installed:
```bash
pip install -r requirements.txt
```

---

## Running Tests

### Run all tests
```bash
python -m pytest
```

### Run tests with verbose output
```bash
python -m pytest -v
```

### Run tests for a specific app
```bash
python -m pytest players/
python -m pytest tournaments/
```

### Run a specific test class or test
```bash
# Run one class
python -m pytest tournaments/tests.py::RoundRobinSchedulerTest

# Run one test
python -m pytest tournaments/tests.py::RoundRobinSchedulerTest::test_generates_correct_number_of_matches
```

---

## Coverage

### Run tests with coverage
```bash
python -m coverage run -m pytest
```

### Show the coverage report in the terminal
```bash
python -m coverage report
```

### Generate an HTML report (open `htmlcov/index.html` in a browser)
```bash
python -m coverage html
```

Coverage configuration is stored in `.coveragerc` in the project root.

---

## Test Structure

### `players/tests.py`
| Class | What is tested |
|--------|----------------|
| `PlayerModelTest` | `__str__`, valid division choices |
| `TeamModelTest` | Auto-name, custom name, `__str__` |
| `PlayerViewTest` | List, add (GET/POST), edit (GET/POST/404) |
| `TeamViewTest` | List, add (GET/POST), edit (GET/404) |

### `tournaments/tests.py`
| Class | What is tested |
|--------|----------------|
| `TournamentModelTest` | `__str__`, all tournament types |
| `DivisionModelTest` | `__str__`, adding teams |
| `MatchModelTest` | `__str__`, default status |
| `RoundRobinSchedulerTest` | Number of matches, status, regeneration, empty division |
| `BracketSchedulerTest` | Number of matches in round 1, round numbering, empty division |
| `GenerateScheduleRouterTest` | Correct scheduler selected per tournament type |
| `TournamentViewTest` | List, detail, 404, generate match programme |
| `MatchResultViewTest` | GET, POST (valid/invalid), 404 |

---

## Current Coverage (latest run)

| Module | Coverage |
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

## Conventions for New Tests

- **Location**: `tests.py` in the relevant app directory.
- **Naming**: Classes start with `Test`, methods start with `test_`.
- **Helper functions**: Use the `make_*` helper functions at the top of the file to create test data.
- **Always cover**: Model `__str__`, view GET/POST, 404 handling, and business logic (for example the scheduler).
- **Isolation**: Use `TestCase` — the database is reset automatically between tests.

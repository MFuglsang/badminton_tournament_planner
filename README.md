# Badminton Tournament Planner

A web-based application for planning and running badminton tournaments.
Handles everything from player registration to match scheduling and result entry.

---

## Features

### Players and pairs
- Create and edit players with name, age, gender and division
- Define your own divisions/categories (e.g. U9, U13, A, B, Beginner) — fully configurable, no hardcoded values
- Create pairs (doubles and mixed doubles) with automatic gender validation
- Filter players by name, gender and division
- View a player's full match schedule across tournaments — ready to print

### Tournament setup
- Create tournaments with date, start time, number of courts and scoring model
- Upload a logo that appears on printed documents
- Create divisions within a tournament with configurable discipline (singles/doubles/mixed) and tournament type:
  - **Round-robin** – everyone plays everyone in the group
  - **Bracket** – direct elimination with seeding
  - **Playoff** – group stage followed by a bracket

### Registration and seeding
- Register players or pairs to divisions directly from the tournament page
- Filter the registration list by name, gender or division with one click
- Assign seed numbers to top players/pairs — seeded players are automatically placed correctly in brackets and groups

### Match programme and schedule
- Automatically generate a match programme for each division
- Generate a time-based schedule that distributes matches across courts and time slots
- Lock the schedule so results can be entered without the plan changing
- **Reset match programme** with one click to start over — match number counter resets to 0

### Results
- Enter results visually with three set boxes per player
- Automatic winner registration and bracket advancement
- Support for walkovers
- Jump directly to a match by number using the search box

### Printouts
- **Match programme** (division by division, sorted by start time)
  - Playoff matches show "Winner of match X vs winner of match Y" instead of cryptic codes
- **Schedule** (time-sorted, all courts combined)
  - Same "Winner of match X" display for finals and semi-finals
- **Score sheets** — one per match, ready to print and place on the court
- **Player schedule** — individual schedule for a single player

### Big screen / display
- Live view of current and upcoming matches for a hall display
- Shows status, court and opponent

### Backup and restore
- Export a tournament as a JSON backup file
- Import a backup to restore a tournament with all divisions, matches and results

---

## Users and access control
- Each club/user logs in with their own account
- Players, pairs and tournaments are tied to the user who created them
- Public tournament view (without login) available for spectators

---

## Getting started

**Docker (recommended for production):**
```bash
cp .env.example .env          # fill in SECRET_KEY, POSTGRES_PASSWORD, ALLOWED_HOSTS
docker compose build
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```
Then open http://localhost/ in your browser.

**Local development:** See [docs/HOW_TO_RUN.md](docs/HOW_TO_RUN.md) for installation instructions.

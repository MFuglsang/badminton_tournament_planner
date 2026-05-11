# System Presentation – Tournament Planner Workflow

Badminton Tournament Planner helps you take a tournament from setup to finish in one place.  
You can register players and teams, build divisions, generate match programmes, plan court/time schedules, and run matches live on the day.

This guide gives a practical walkthrough in the same order a tournament planner typically works, so it can be used as both an introduction and an operations checklist.

---

## 1. Creating players and teams

**What it does:** Creates the participant base the tournament is built from.  
**Why it matters:** Correct player and team data ensures registration, match generation, and results are reliable later.

1. Go to **Players** (`/players/`) and create all players.
2. Go to **Teams** (`/players/teams/`) and create the doubles/mixed teams you need.
3. Check that names and categories/divisions are correct before tournament setup.

![Screenshot placeholder: Players list and add player form](screenshots/01-players-and-teams.png)

---

## 2. Creating a tournament

**What it does:** Creates the event container with date/time, courts, and scoring setup.  
**Why it matters:** Tournament settings are used by schedule generation, printouts, and daily operations.

1. Open **Tournaments** (`/tournaments/`).
2. Click **Create tournament**.
3. Enter tournament data (name, date, start time, number of courts, scoring model, logo if needed).
4. Save the tournament.

![Screenshot placeholder: Create tournament form](screenshots/02-create-tournament.png)

---

## 3. Adding divisions

**What it does:** Splits the tournament into playable categories and formats.  
**Why it matters:** Divisions define who can play each other and which competition model is used.

1. Open the tournament detail page.
2. In **Create new division**, enter:
   - division name
   - discipline (single/double/mixed)
   - tournament type (round-robin/bracket/playoff)
3. Save each division.
4. Register players/teams inside each division.

![Screenshot placeholder: Tournament page with create division and participant registration](screenshots/03-add-divisions.png)

---

## 4. Creating match programme for divisions

**What it does:** Generates the match list for each division based on participants and format.  
**Why it matters:** This is the foundation for the time schedule and for tracking match progress/results.

1. On the tournament detail page, open each division block.
2. Click **Generate match programme** for the division.
3. Verify that matches are created correctly (participants, order, labels).
4. Repeat for all divisions.

![Screenshot placeholder: Division with generated match programme](screenshots/04-generate-match-programme.png)

---

## 5. Creating play schedule for the tournament

**What it does:** Places all generated matches into time slots and courts.  
**Why it matters:** A clear schedule reduces waiting time, court conflicts, and manual coordination during the event.

1. Open **Time schedule** from the tournament page.
2. Click **Generate time schedule**.
3. Review assigned courts and times.
4. Optionally adjust in **Manual editor**.
5. When ready, click **Lock schedule**.

![Screenshot placeholder: Time schedule page with generated schedule](screenshots/05-create-play-schedule.png)

---

## 6. Running the tournament

**What it does:** Supports live execution of matches, status handling, and result entry.  
**Why it matters:** Keeps the event flow updated in real time and ensures standings/brackets stay correct.

1. Open **Tournament run**.
2. Start matches with **Start**.
3. Enter results with **Result** (or **WO** for walkover).
4. Follow progress per division until all matches are complete.
5. Use **Big screen** for hall display if needed.

![Screenshot placeholder: Tournament run page during live execution](screenshots/06-running-the-tournament.png)

---

## PDF export

Open this Markdown file in your preferred editor/viewer and export/print to PDF.

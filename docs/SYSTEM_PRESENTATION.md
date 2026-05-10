# System Presentation – Tournament Planner Workflow

This document is a functional presentation of the system seen from a tournament planner’s perspective.  
It is written in Markdown and can be exported to PDF.

---

## 1. Creating players and teams

1. Go to **Players** (`/players/`) and create all players.
2. Go to **Teams** (`/players/teams/`) and create the doubles/mixed teams you need.
3. Check that names and categories/divisions are correct before tournament setup.

![Screenshot placeholder: Players list and add player form](screenshots/01-players-and-teams.png)

---

## 2. Creating a tournament

1. Open **Tournaments** (`/tournaments/`).
2. Click **Create tournament**.
3. Enter tournament data (name, date, start time, number of courts, scoring model, logo if needed).
4. Save the tournament.

![Screenshot placeholder: Create tournament form](screenshots/02-create-tournament.png)

---

## 3. Adding divisions

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

1. On the tournament detail page, open each division block.
2. Click **Generate match programme** for the division.
3. Verify that matches are created correctly (participants, order, labels).
4. Repeat for all divisions.

![Screenshot placeholder: Division with generated match programme](screenshots/04-generate-match-programme.png)

---

## 5. Creating play schedule for the tournament

1. Open **Time schedule** from the tournament page.
2. Click **Generate time schedule**.
3. Review assigned courts and times.
4. Optionally adjust in **Manual editor**.
5. When ready, click **Lock schedule**.

![Screenshot placeholder: Time schedule page with generated schedule](screenshots/05-create-play-schedule.png)

---

## 6. Running the tournament

1. Open **Tournament run**.
2. Start matches with **Start**.
3. Enter results with **Result** (or **WO** for walkover).
4. Follow progress per division until all matches are complete.
5. Use **Big screen** for hall display if needed.

![Screenshot placeholder: Tournament run page during live execution](screenshots/06-running-the-tournament.png)

---

## PDF export

Open this Markdown file in your preferred editor/viewer and export/print to PDF.

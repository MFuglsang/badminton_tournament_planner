# User Guide: Tournament-Day Page

The tournament-day page is the main workspace during the event itself. It gives you a complete overview of all matches, active matches, and the next matches that should be started.

---

## Page Layout

The page is divided into two columns:

- **Left column** — all divisions and their matches
- **Right column (sidebar)** — matches currently in progress, the next matches to start, and shortcuts

At the top of the page there is a **progress bar** showing how many matches have been completed out of the total number of matches.

---

## Progress Bar

```
24 / 60 matches completed      3 in progress
████████░░░░░░░░░░░░░░░
```

- The **green area** grows as matches are completed
- When all matches are done, the page shows: **✓ All matches completed**

---

## Search

At the top of the left column there is a search field. You can search by:

- **Match number** — for example `#42`
- **Player name or team name** — for example `Hansen`

Matching matches are highlighted with a yellow background across all divisions.

---

## Divisions (left column)

Each division can be expanded or collapsed by clicking its header. The header shows:

| Element | Meaning |
|---|---|
| Division name | Name of the event, for example "Mixed Double A" |
| Discipline | Singles, doubles, and so on |
| 🔵 **X in progress** | Number of matches that have started but are not yet finished |
| 🟡 **X waiting** | Number of matches that still need to be started |
| 🟢 **X finished** | Number of completed matches |
| ✓ **Finished** | All matches in the division have been completed |

### Tabs inside a division

When a division is expanded, you can switch between three tabs:

#### Matches
Shows all waiting and in-progress matches in the division.

For each match the page shows:
- **#number** and scheduled time
- **Players/teams** with optional seeding and status icons
- **Buttons** to start the match or record the result

Status icons next to player names:
- 🏸 — the player is currently playing another match
- ⚠ **Busy** — shown instead of the Start button if a player is busy or resting

Completed matches are collapsed under **"Completed matches (X)"** and can be expanded when needed. Results can be corrected there.

#### Standings
Shows the current standings in the division (group stage / playoff).

Columns: Played (P), Won (W), Lost (L), Points (Pts), Sets, and Score.

A green arrow ↑ shows which teams advance to the playoff stage.

Status dots:
- 🟢 — player is currently in a match
- 🟡 — player is resting

#### Bracket / Playoff
Shows the bracket view for divisions with elimination matches.

---

## Sidebar (right column)

### ⚡ Matches in Progress
Shown only when there are active matches. For each running match you can directly:
- Click **Result** to record the outcome
- Click **WO** to record a walkover

### 🏸 Next Matches
Shows up to the next 5 waiting matches (sorted by time) where none of the players are busy. Click **▶ Start** to start a match directly from here.

---

## Typical Workflow on Tournament Day

1. **Open the tournament-day page** and keep it open in the browser all day
2. **Check sidebar → Next matches** to see who should go on court
3. Click **▶ Start** for the relevant match
4. When the match ends, go to **⚡ In progress** and click **Result**
5. Record the result — the page refreshes automatically every 60 seconds

---

## Big Screen

Click **📺 Big screen** at the top of the page to open a big-screen view in a new window. It shows the next 5 matches and is optimized for display on an external screen in the hall. The big-screen view refreshes automatically.

---

## Tips

- The tournament-day page refreshes automatically. Reload the page manually if you want the newest data immediately (F5 / Cmd+R).
- Use the **search field** to quickly find a specific match number or player name when someone asks when they are playing.
- The page does not remember which divisions were expanded after a reload, so expand the active divisions again at the start of the day.

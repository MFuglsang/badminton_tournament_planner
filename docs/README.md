# Badminton Tournament Planner

## Overview
The Badminton Tournament Planner is a Django-based web application designed to help users manage badminton tournaments. It includes features for managing players, teams, tournaments, and matches. The application is localized in Danish and English and provides an admin interface for advanced management tasks.

---

## Features
- **Player and Team Management**: Add, edit, and view players and teams.
- **Tournament Setup**: Create and manage tournaments, divisions, and matches.
- **Match Scheduling**: Auto-generate match programs based on tournament type (round-robin or bracket).
- **Match Results**: Record results and winners per match directly from the web interface.
- **Admin Interface**: A powerful admin panel for managing all aspects of the application.
- **Localization**: Support for Danish and English languages.
- **Responsive Design**: Works seamlessly on desktop and mobile devices.

---

## URL Structure
| URL | Description |
|-----|-------------|
| `/` | Homepage with links to all sections |
| `/tournaments/` | List of all tournaments |
| `/tournaments/<id>/` | Tournament detail with divisions and match schedule |
| `/tournaments/division/<id>/generate/` | Generate match schedule for a division (POST) |
| `/tournaments/match/<id>/result/` | Record result for a match |
| `/players/` | List of all players |
| `/players/add/` | Add a new player |
| `/players/teams/` | List of all teams |
| `/admin/` | Django admin panel |

---

## Project Structure
- `players/`: Models, views, forms, and templates for managing players and teams.
- `tournaments/`: Models, views, forms, templates, and scheduler for managing tournaments, divisions, and matches.
  - `scheduler.py`: Logic for generating round-robin and bracket match schedules.
- `matches/`: App reserved for future standalone match features.
- `tournament_planner/`: Main project folder with settings and URL configurations.
- `tournament_planner/templates/`: Project-level templates (homepage).
- `docs/`: Documentation files.

---

## How to Run the Application
See the `HOW_TO_RUN.md` file for detailed instructions on setting up and running the application.
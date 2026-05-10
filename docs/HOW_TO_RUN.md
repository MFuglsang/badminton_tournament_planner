# How to Run the Badminton Tournament Planner

## Prerequisites
1. **Python**: Ensure Python 3.13.9 or higher is installed.
2. **Virtual Environment**: Use a virtual environment to manage dependencies.
3. **Django**: The application is built using Django 6.0.4.

---

## Setup Instructions

### 1. Clone the Repository
```bash
git clone <repository-url>
cd badminton_tournament_planner
```

### 2. Create and Activate a Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
.venv\Scripts\activate.bat    # Windows Command Prompt
.venv\Scripts\Activate.ps1    # Windows PowerShell
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Apply Migrations
```bash
python manage.py migrate
```

### 5. Create a Superuser
```bash
python manage.py createsuperuser
```
Follow the prompts to set up an admin account.

### 6. Start the Development Server
```bash
python manage.py runserver
```

---

## Access the Application
- **Homepage**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Tournaments**: [http://127.0.0.1:8000/tournaments/](http://127.0.0.1:8000/tournaments/)
- **Players**: [http://127.0.0.1:8000/players/](http://127.0.0.1:8000/players/)
- **Admin Panel**: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

---

## Workflow: Set Up and Run a Tournament

1. **Create players** via `/admin/players/player/add/` or `/players/add/`.
2. **Create teams** (pairs of players) via `/admin/players/team/add/` or `/players/teams/add/`.
3. **Create a tournament** via `/admin/tournaments/tournament/add/`.
4. **Create divisions** under the tournament via `/admin/tournaments/division/add/`, then add teams to each division.
5. **Generate the match programme** by visiting the tournament page (`/tournaments/<id>/`) and clicking **Generate match programme** for a division.
6. **Record results** by clicking **Record result** for the individual matches.

---

## Notes
- Ensure `DEBUG = True` in `settings.py` for development.
- For production, configure `ALLOWED_HOSTS` and set `DEBUG = False`.
- Templates for the project homepage are in `tournament_planner/templates/`.
- App-specific templates are in `<app>/templates/<app>/`.

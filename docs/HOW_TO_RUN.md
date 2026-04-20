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
source .venv/Scripts/activate  # On Windows
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

## Workflow: Opsæt og kør en turnering

1. **Opret spillere** via `/admin/players/player/add/` eller `/players/add/`.
2. **Opret hold** (par af spillere) via `/admin/players/team/add/` eller `/players/teams/add/`.
3. **Opret en turnering** via `/admin/tournaments/tournament/add/`.
4. **Opret divisioner** under turneringen via `/admin/tournaments/division/add/`, og tilføj hold til divisionen.
5. **Generer kampprogram** ved at besøge turneringens side (`/tournaments/<id>/`) og klikke "Generer kampprogram" for en division.
6. **Registrer resultater** ved at klikke "Registrer resultat" ved de enkelte kampe.

---

## Notes
- Ensure `DEBUG = True` in `settings.py` for development.
- For production, configure `ALLOWED_HOSTS` and set `DEBUG = False`.
- Templates for the project homepage are in `tournament_planner/templates/`.
- App-specific templates are in `<app>/templates/<app>/`.
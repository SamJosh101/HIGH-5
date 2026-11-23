# HIGH 5 – Online Transportation & Bus Ticket Booking Management System

A web platform where passengers search bus trips, choose seats, book tickets and manage their bookings, and administrators manage routes, buses, schedules, fares, bookings and reports.

**Client / academic project:** BASCODETECH
**Stack:** Python 3.12 · Django 5.2 LTS · MySQL 8.x · HTML · CSS · JavaScript · Bootstrap 5

| Team member | Area |
|---|---|
| Sam Josh (lead) | Project setup, database architecture, authentication, security, reviews |
| Raheem | Trip search, seat selection, bookings, cancellation, passenger dashboard |
| Daniel | Routes, buses, schedules, fares, admin dashboard, reports |
| Cross | Homepage, layouts, styling, documentation, screenshots, UI testing |

Docs: [Architecture](docs/ARCHITECTURE.md) · [Database contract](docs/DATABASE.md) · [Contributing](CONTRIBUTING.md)

---

## Setup (Windows, PowerShell)

### Prerequisites
* Python **3.12** (`py -3.12 --version`)
* MySQL Server **8.x** running locally
* Git

### 1. Clone the repository
```powershell
git clone <repository-url> HIGH-5
cd HIGH-5
```

### 2. Create and activate a virtual environment
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```
If PowerShell blocks the script, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
(macOS/Linux: `python3.12 -m venv .venv` then `source .venv/bin/activate`.)

### 3. Install dependencies
```powershell
pip install -r requirements.txt
```

### 4. Configure MySQL
Edit `docs/setup_mysql.sql` locally, replace `CHANGE_THIS_PASSWORD`, then run it as root (don't commit the edited password):
```powershell
mysql -u root -p -e "source docs/setup_mysql.sql"
```
This creates the `high5_db` database (utf8mb4), a `high5_user` account, and permission for the test database `test_high5_db`.

### 5. Configure environment variables
```powershell
Copy-Item .env.example .env
```
Open `.env` and set:
* `DJANGO_SECRET_KEY` – generate one with
  `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"`
* `DB_PASSWORD` – the password you chose in step 4.
* `DEMO_ADMIN_PASSWORD` and `DEMO_PASSENGER_PASSWORD` – passwords of your choice for the test accounts (step 7).

`.env` is git-ignored. **Never commit it.**

### 6. Apply migrations
```powershell
python manage.py migrate
```

### 7. Create the test accounts and sample trips
```powershell
python manage.py seed_demo
```
This creates two test accounts and a week of trips on five Nigerian routes (Lagos → Abuja, Lagos → Ibadan, Lagos → Benin City, Abuja → Kaduna, Port Harcourt → Enugu), so the homepage, Book a Trip and the admin pages have data straight away. It is safe to run again (for example the next week, to add new trips).

**Default test logins**

| Role | Email | Password |
|---|---|---|
| Administrator | `admin@high5.test` | the value of `DEMO_ADMIN_PASSWORD` in your `.env` |
| Passenger | `passenger@high5.test` | the value of `DEMO_PASSENGER_PASSWORD` in your `.env` |

The passwords are deliberately not written in the code or this README (no hard-coded passwords); each person sets them in their own `.env`. `seed_demo` only runs when `DJANGO_DEBUG=True`.

To create your own administrator instead, run `python manage.py createsuperuser` (superusers get the `ADMIN` role and a verified email automatically).

New passengers who sign up must click the link in their verification email before they can log in. In development that email is printed in the `runserver` terminal.

### 8. Run the development server
```powershell
python manage.py runserver
```
Open http://127.0.0.1:8000/

### Running tests
```powershell
python manage.py test
```
Tests use a separate database (`test_high5_db`) that Django creates and deletes automatically.

> **Temporary SQLite mode:** if MySQL is unavailable you can run `$env:DB_ENGINE="sqlite"; python manage.py test` for quick isolated checks. This is **not** the project database and does not meet the MySQL requirement.

---

## Main URLs

| URL | Who | Purpose |
|---|---|---|
| `/` | everyone | Homepage |
| `/accounts/register/` · `/accounts/login/` | everyone | Passenger sign-up / log in |
| `/accounts/profile/` | logged-in | Profile, change password |
| `/accounts/password/reset/` | everyone | Password reset (email printed in terminal in development) |
| `/bookings/search/` | passengers | Book a Trip: search, choose a trip, book seats; logged-out visitors are sent to login and back |
| `/bookings/dashboard/` | passengers | My Bookings and ticket pages |
| `/transport/manage/` | admins | Manage routes, buses and schedules |
| `/dashboard/` | admins | Admin dashboard, bookings and reports |
| `/django-admin/` | superusers | Django's built-in admin site |

## Project structure
```
config/        settings, root URLs
accounts/      custom user, auth, role permissions (accounts/permissions.py)
transport/     routes, buses, schedules, fares
bookings/      search, seats, bookings
dashboard/     admin dashboard, reports
templates/     base.html, partials/, one folder per app
static/        css/high5.css, js/high5.js, images/
docs/          architecture, database contract, MySQL setup script
```

## Project status
**Phase 1 – Foundation:** done (project setup, custom user, authentication, role permissions, base templates, docs, tests).
**Phase 2 – Core features:** transport management (Daniel), booking and cancellation (Raheem), email verification (Cross), real Popular Routes and test data (Sam).
**Still to do:** admin "mark as paid", trips becoming Completed after departure, editing past schedules, optional seat selection.

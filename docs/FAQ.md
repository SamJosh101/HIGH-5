# HIGH 5 – Frequently Asked Questions

## What is HIGH 5?

HIGH 5 is an online transportation and bus ticket booking management system developed for BASCODETECH. It lets passengers search bus trips, select seats, book tickets, and manage their bookings, while administrators manage routes, buses, schedules, fares, bookings, and reports.

## What technologies does the project use?

- Python 3.12
- Django 5.2 LTS
- MySQL 8.x
- HTML and CSS
- JavaScript
- Bootstrap 5
- `mysqlclient`
- `python-dotenv`

## Which parts of the project are complete?

Phase 1 (Foundation) is complete. It includes project setup, the custom user model, authentication, role permissions, base templates, documentation, and tests.

## Which features are still in development?

The repository identifies the following areas as in progress:

- Trip search and seat selection
- Passenger bookings and cancellations
- Passenger dashboard
- Route, bus, and schedule management
- Fare management
- Administrator dashboard and reports

## Who can use the system?

The project has passenger and administrator roles:

- **Passengers** can search trips, make bookings, and view or cancel their own bookings.
- **Administrators** can manage transport data and access the administrative dashboard.
- **Superusers** can use Django's built-in administration site and receive the `ADMIN` role automatically.

## What are the setup prerequisites?

You need:

- Python 3.12
- MySQL Server 8.x running locally
- Git
- `pip` for installing dependencies

## How do I set up HIGH 5 locally on Windows?

1. Clone the repository:

   ```powershell
   git clone <repository-url> HIGH-5
   cd HIGH-5
   ```

2. Create and activate a virtual environment:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

4. Configure MySQL using `docs/setup_mysql.sql`.

5. Copy the environment template:

   ```powershell
   Copy-Item .env.example .env
   ```

6. Set `DJANGO_SECRET_KEY` and `DB_PASSWORD` in `.env`.

7. Apply database migrations:

   ```powershell
   python manage.py migrate
   ```

8. Create an administrator:

   ```powershell
   python manage.py createsuperuser
   ```

9. Start the development server:

   ```powershell
   python manage.py runserver
   ```

Open `http://127.0.0.1:8000/` in a browser.

## What database does the project use?

MySQL 8.x is the official project database. The setup script creates:

- `high5_db` for application data
- `high5_user` as the application database account
- `test_high5_db` for tests

See [DATABASE.md](DATABASE.md) for the database contract and model rules.

## Can I use SQLite instead of MySQL?

SQLite is available only as a temporary fallback for isolated tests:

```powershell
$env:DB_ENGINE="sqlite"
python manage.py test
```

It does not replace the MySQL database and is not sufficient for final MySQL-based testing.

## How do I run the tests?

Run:

```powershell
python manage.py test
```

Tests use Django's separate `test_high5_db` database, which is created and deleted automatically.

## How does password reset work during development?

The default email backend prints password-reset emails in the terminal. No external email provider is required for local development.

## What must I configure in `.env`?

Important values include:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT`
- `TIME_ZONE`
- `CURRENCY_SYMBOL`

The project uses `Africa/Lagos` for its time zone and `₦` for the Nigerian Naira currency symbol.

## How should environment secrets be handled?

Never commit `.env`, passwords, secret keys, tokens, or other credentials. `.env` is git-ignored, and `.env.example` should contain placeholders only.

## How is seat availability calculated?

Available seats equal:

```text
bus total seats - confirmed seats for the schedule
```

Cancelled bookings are excluded, so cancellation automatically releases their seats. Booking creation and cancellation use database transactions and row locks to prevent overbooking under concurrent requests.

## How are cancellations restricted?

Cancellations must occur before the configured cutoff time. The default is 24 hours before departure and can be changed through `BOOKING_CANCELLATION_CUTOFF_HOURS`.

## How is the application organized?

- `accounts/` – custom user model, authentication, and role permissions
- `transport/` – routes, buses, schedules, and fares
- `bookings/` – trip search, seats, and bookings
- `dashboard/` – administrator dashboard and reports
- `config/` – Django settings and root URLs
- `templates/` – Django HTML templates
- `static/` – CSS, JavaScript, and images
- `docs/` – architecture, database, setup, and project documentation

See [ARCHITECTURE.md](ARCHITECTURE.md) for request flow and app dependencies.

## How do team members contribute?

The project uses separate feature branches:

- `main` – protected stable branch
- `samjosh-backend` – shared backend, settings, authentication, and documentation
- `raheem-booking` – booking and passenger features
- `daniel-transport` – transport and administration features
- `cross-frontend` – templates, styles, and UI work

Changes must be submitted through pull requests into `main`.

## What pull request checks are required?

Before merging, contributors should:

- Run `python manage.py test` on MySQL.
- Run `python manage.py makemigrations --check --dry-run`.
- Commit migration files with model changes.
- Keep pull requests small and focused.
- Obtain at least one approval.
- Describe changes and testing performed.
- Add screenshots for UI changes.

## What files should never be committed?

Do not commit:

- `.env`
- `.venv/`
- SQLite database files
- `staticfiles/`
- Uploaded `media/` files
- Editor folders such as `.vscode/` or `.idea/`
- Passwords, secret keys, or tokens

## Where should I put project documentation?

Architecture and database details belong in `docs/`. General setup and project entry-point information belong in `README.md`. Contributing rules belong in `CONTRIBUTING.md`.

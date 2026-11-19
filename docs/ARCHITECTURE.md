# HIGH 5 – Architecture

**HIGH 5 – Online Transportation & Bus Ticket Booking Management System** (BASCODETECH)

Stack: Python 3.12 · Django 5.2 LTS · MySQL 8.x · HTML/CSS/JS · Bootstrap 5.3 (CDN).
The teacher's SRS is the source of truth; open questions are listed in [DATABASE.md](DATABASE.md#5-open-questions-must-be-confirmed-against-the-srs).

## 1. Why this structure

Django splits a project into small **apps**, each responsible for one area. One owner per app means teammates rarely edit the same files, which keeps Git merges painless.

| App | Owner | Responsibility | URL prefix / namespace |
|---|---|---|---|
| `config/` | Sam | Settings, root URLs, WSGI/ASGI | – |
| `accounts` | Sam | Custom user, register/login/logout, password reset, profile, **role permissions** | `/accounts/` · `accounts:` |
| `transport` | Daniel | Route, Bus, Schedule, fares – admin management pages | `/transport/` · `transport:` |
| `bookings` | Raheem | Trip search, seats, booking, cancellation, history, passenger dashboard | `/bookings/` · `bookings:` |
| `dashboard` | Daniel | Administrator dashboard, revenue, reports (reads other apps' models) | `/dashboard/` · `dashboard:` |
| `templates/`, `static/` | Cross | Base layout, partials, styling, homepage | – |

`/django-admin/` is Django's built-in admin site, kept for superuser maintenance. The real HIGH 5 admin interface is `/dashboard/` and `/transport/manage/`.

**Dependency direction** (who may import whom):
`accounts` ← `transport` ← `bookings` ← `dashboard`.
`transport` must never import from `bookings` (avoids circular imports). `dashboard` only reads.

## 2. Request flow

```
Browser ──► config/urls.py ──► <app>/urls.py ──► view (permission decorator)
                                                  │
                                    forms.py (server-side validation)
                                                  │
                                 services.py (business rules, transactions)
                                                  │
                                       models.py (ORM) ──► MySQL
                                                  │
                                 templates/<app>/*.html (extends base.html)
```

Guideline: keep views thin. Business rules that touch several models (booking, cancellation, revenue) go in `<app>/services.py` so they can be tested directly and reused.

## 3. Authentication & authorisation

* **Custom user model** `accounts.User` (email login, `role` = ADMIN/PASSENGER), set via `AUTH_USER_MODEL` **before the first migration**.
* Public registration only ever creates **PASSENGER** accounts. ADMIN accounts are created with `createsuperuser` or by an existing admin in `/django-admin/`.
* Passwords are hashed by Django (PBKDF2-SHA256 with salt). Django's password validators reject short/common/numeric passwords.
* Logout is **POST-only** (Django 5), so a malicious link cannot log someone out.
* Password reset uses Django's signed, expiring, single-use tokens. In development emails are printed to the terminal.
* After login, `accounts:after_login` sends admins to `dashboard:home` and passengers to `bookings:dashboard`.

### Role rules – use on EVERY protected view

```python
from accounts.permissions import admin_required, passenger_required, AdminRequiredMixin

@admin_required          # Daniel's transport + dashboard views
def route_list(request): ...

@passenger_required      # Raheem's booking views
def my_bookings(request): ...
```

* Anonymous → redirect to login. Logged in with the wrong role → **403**.
* **Object ownership (rule 4)**: a passenger may only see their own bookings. Always filter by owner – never fetch by ID alone:

```python
booking = get_object_or_404(Booking, booking_ref=ref, passenger=request.user)
```

Returning 404 (not 403) for other people's bookings avoids revealing that a reference exists.

### Why the custom user model must be decided first

The user table is referenced by foreign keys from Django's own tables (admin log, sessions, permissions) and from ours (bookings). Changing `AUTH_USER_MODEL` after migrations have run means those foreign keys point at the wrong table. Django cannot migrate that automatically: in practice you must delete the database and all migrations and start again, losing data. So the model is in place from migration `accounts.0001_initial`, and new *fields* can still be added later with normal migrations.

## 4. Business rules (from the brief) and where they live

| # | Rule | Where enforced |
|---|---|---|
| 1 | No booking beyond bus capacity | `bookings/services.py` inside `transaction.atomic()` + `select_for_update()` |
| 2 | Only active routes & buses in search | `Schedule` queryset filter in search view (Raheem) |
| 3 | Unique booking reference | `unique=True` on `booking_ref` + retry on collision |
| 4 | Passengers see only their bookings | Filter by `passenger=request.user` |
| 5 | Admins see all bookings | `@admin_required` views in `dashboard` |
| 6 | Passengers cannot open admin pages | `@admin_required` (tested in `accounts/tests.py`) |
| 7 | Cancellation releases seats | Seats counted only from CONFIRMED bookings |
| 8 | No cancellation after cut-off | Service checks `settings.BOOKING_CANCELLATION_CUTOFF_HOURS` |
| 9 | Atomic booking operations | `@transaction.atomic` on service functions |
| 10 | No overbooking under concurrency | Row lock on the Schedule with `select_for_update()` |

Frontend (JavaScript) checks are only for convenience. **The server always re-validates.**

## 5. Configuration and security

* All secrets come from `.env` (loaded by `python-dotenv`); `.env` is git-ignored, `.env.example` documents the keys.
* `DJANGO_DEBUG=False` in production turns on secure cookies, HTTPS redirect and HSTS settings.
* CSRF middleware, clickjacking protection (`X_FRAME_OPTIONS=DENY`), HttpOnly session cookies (8 h) are on.
* MySQL runs in strict mode with `utf8mb4` so invalid data is rejected and all characters are stored correctly.

### SQLite fallback (temporary only)

`DB_ENGINE=sqlite` switches to a local SQLite file **only for isolated testing when MySQL is unavailable**. It does **not** satisfy the MySQL requirement. Before submission, all tests must pass with `DB_ENGINE=mysql`.

## 6. Templates and frontend conventions (Cross)

* **One look everywhere:** the dark theme from the landing page. `base.html` sets Bootstrap's dark mode, and `static/css/high5.css` restyles Bootstrap buttons, forms, alerts and cards to match. So a teammate's page that uses normal Bootstrap classes already fits in.
* Every page: `{% extends "base.html" %}` and fills `{% block title %}` and `{% block content %}` (optional: `extra_css`, `extra_js`, `main_class`, `body_class`, and `navbar` / `messages` / `footer` to replace those parts).
* **Keep text short.** A heading, the controls and a button: users should understand a page in a few seconds. Developer notes go in `{% comment %}`, never on the page.
* Inner pages: start with `<div class="h5-page-head"><h1>…</h1></div>`, put content in `<div class="h5-panel">`, and show empty lists with the `h5-empty` block (see `templates/bookings/dashboard.html`).
* Login, sign-up and password reset pages extend `accounts/auth_base.html` (split screen with the animated bus scene).
* Navigation (`partials/navbar.html` + `partials/nav_links.html`) shows links by role: visitors see Book a Trip, Routes, Support; passengers also see My Bookings and History; admins see Dashboard, Transport, Routes, Support. The current page is highlighted automatically.
* The trip search bar is `partials/search_bar.html` (homepage and search page).
* Homepage: `templates/home.html` + `static/css/home.css` + `static/js/home.js`. Popular-route cards use placeholder data from `config/views.py` until the transport models exist. All animations respect the OS "reduce motion" setting.
* Templates live in `templates/<app>/<page>.html`. Shared pieces live in `templates/partials/`.
* Forms: render with `{% include "partials/form_fields.html" %}`; Python forms inherit `accounts.forms.BootstrapFormMixin` to get Bootstrap classes.
* Links: always `{% url 'namespace:name' %}`.
* CSS: `static/css/high5.css`. Use the `--h5-*` variables; prefix custom classes with `h5-`.
* JS: `static/js/high5.js` for site-wide behaviour; page-specific scripts go in `static/js/<page>.js` loaded via `{% block extra_js %}`.

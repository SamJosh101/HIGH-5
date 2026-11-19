# Contributing to HIGH 5

## Branches

| Branch | Owner | Works in |
|---|---|---|
| `main` | protected | Stable, reviewed code only. **No direct commits.** |
| `samjosh-backend` | Sam | `config/`, `accounts/`, `docs/`, shared conventions |
| `raheem-booking` | Raheem | `bookings/`, `templates/bookings/` |
| `daniel-transport` | Daniel | `transport/`, `dashboard/`, `templates/transport/`, `templates/dashboard/` |
| `cross-frontend` | Cross | `templates/base.html`, `templates/partials/`, `templates/home.html`, `static/`, `README.md` |

Sam should turn on GitHub branch protection for `main` (Settings → Branches): require a pull request and at least 1 approval before merging.

## Daily workflow

```powershell
git checkout main
git pull origin main
git checkout raheem-booking        # your own branch
git merge main                     # bring in teammates' merged work
# ... work, then:
git add <files>
git commit -m "bookings: add seat availability calculation"
git push origin raheem-booking
```

Then open a **Pull Request** into `main` on GitHub.

## Pull Request rules

1. Keep PRs small and focused (one feature).
2. `python manage.py test` must pass, **on MySQL**.
3. `python manage.py makemigrations --check --dry-run` must report "No changes detected" (all migrations committed).
4. At least one reviewer approves. Sam reviews anything touching models, migrations, settings, permissions or money.
5. Describe what changed, how you tested it, and add screenshots for UI changes.
6. Never force-push to `main` or to someone else's branch.

## Commit messages

`<area>: <what changed>` in the present tense, e.g. `transport: add Route model`, `frontend: style login page`.

## Migrations – the rules that prevent conflicts

* Only the **owner of an app** runs `makemigrations` for that app (`python manage.py makemigrations transport`).
* Model changes must match [docs/DATABASE.md](docs/DATABASE.md). If the contract needs to change, update the doc in the same PR.
* Always commit the migration file together with the model change.
* Never edit or delete a migration that is already merged into `main`. Create a new one.
* If you get a migration conflict after merging `main`, ask Sam before running `makemigrations --merge`.
* `bookings` migrations depend on `transport`, so Daniel's models merge first.

## Never commit

* `.env` or any password, secret key or token
* `.venv/` (virtual environment)
* `*.sqlite3`, `staticfiles/`, uploaded `media/` files
* Editor folders (`.vscode/`, `.idea/`)

`.gitignore` already blocks these, but check `git status` before every commit.

## Coding conventions

* Follow PEP 8. Use 4 spaces. Meaningful names.
* Never duplicate a model. Import it: `from transport.models import Schedule`.
* Use `settings.AUTH_USER_MODEL` / `get_user_model()` for users.
* Money: `DecimalField`, never `float`.
* Every protected view uses `admin_required` / `passenger_required` (or the mixins) from `accounts.permissions`.
* Validate on the server (forms/services), not only in JavaScript.
* Booking/cancellation logic lives in `bookings/services.py` with `transaction.atomic()` and `select_for_update()`.
* Every feature comes with tests in the app's `tests.py`.
* Templates extend `base.html`. Link with `{% url %}`.

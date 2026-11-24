# HIGH 5 – Email verification (6-digit code)

New passengers must prove they own their email address before they can log in.
The flow was first built by Cross with a signed link; it now uses a one-time
**6-digit code (OTP)** that the user types on the site.

## How it works

1. **Sign up** (`/accounts/register/`). The account is saved with `email_verified = False`,
   the user is *not* logged in, and a code is emailed to them.
2. **Verify** (`/accounts/verify-email/`). The page asks for the email address
   (already filled in after sign-up) and the 6-digit code.
3. A correct code marks the account verified and sends the user to the login page.
4. Until then, logging in is refused with "Verify your email address before signing in".

Code rules (`accounts/email_verification.py`):

| Rule | Value |
|---|---|
| Length | 6 digits, made with Python's `secrets` module |
| Stored as | a hash only (`EmailVerificationCode.code_hash`, like a password) – never the code itself |
| Expires after | 10 minutes (`CODE_VALID_MINUTES`) |
| Wrong tries allowed | 5 (`MAX_ATTEMPTS`); after that the code stops working |
| New code | `/accounts/verify-email/resend/`, at most one per address and IP per minute; it replaces the old code |
| Used code | deleted, so it cannot be used twice |

Every failure (wrong, expired, used-up code, unknown or already-verified address) shows the same
message, and "send a new code" gives the same answer for every address, so the pages never reveal
which email addresses have accounts.

The email address waiting for its code and the page to return to (`next`) are kept in the
**session**, never in the URL.

## Returning to the page the user started from

If the visitor signed up from a protected page (for example by clicking a Popular Route, which
sends them to log in with `?next=`), sign-up keeps that safe `next`. After verifying, they go to the
login page with the same `next`, and after logging in they land on the pre-filled Book a Trip search.
Unsafe `next` values (other websites) are dropped by `accounts.views._safe_next`.

## Where the email goes

In development, `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` (in `.env`) prints the
email, including the code, in the `runserver` terminal. Nothing reaches a real inbox.

Sending real email (for example through Gmail) is **not set up yet**: `config/settings.py` would also
need to read `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` and `EMAIL_USE_TLS`
from `.env`. Keep those credentials in `.env` only, never in the code.

## Accounts created before verification existed

Migration `0003_verify_existing_accounts` marks them verified, so nobody is locked out.
Superusers made with `createsuperuser` are verified automatically.

```powershell
python manage.py migrate
python manage.py test accounts
```

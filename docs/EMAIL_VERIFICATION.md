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

`config/settings.py` reads all email settings from `.env` (SMTP settings added by Cross).
Tests always use Django's in-memory mail box, so they never send real email.

### Development: console (default in `.env.example`)

`EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` prints the email, including the
code, in the `runserver` terminal. Nothing reaches a real inbox.

### Real inboxes: Gmail SMTP

1. Use a Gmail account for the project and turn on **2-Step Verification**
   (Google Account → Security).
2. Create an **App Password** (Google Account → Security → App passwords). Google shows a
   16-letter password once. Gmail refuses the normal account password for SMTP.
3. Put these in your own `.env` (never in the code, never committed):

   ```
   EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_USE_TLS=True
   EMAIL_USE_SSL=False
   EMAIL_HOST_USER=<the Gmail address>
   EMAIL_HOST_PASSWORD=<the 16-letter app password>
   DEFAULT_FROM_EMAIL=HIGH 5 <the Gmail address>
   ```

4. Restart `runserver`, sign up with an address you can open, and check the inbox (and Spam).

`EMAIL_USE_TLS` and `EMAIL_USE_SSL` cannot both be `True` (settings refuse to start). Port 587
uses TLS; port 465 uses SSL.

### If sending fails

`accounts.services.send_email_verification` catches the error and logs it (user id only, never
the code or the password) instead of showing a server error. The account is still created, the
user is sent to the code page with a warning, and can use "Send a new code" a minute later.
Password-reset emails behave the same way (Django logs the failure).

## Accounts created before verification existed

Migration `0003_verify_existing_accounts` marks them verified, so nobody is locked out.
Superusers made with `createsuperuser` are verified automatically.

```powershell
python manage.py migrate
python manage.py test accounts
```

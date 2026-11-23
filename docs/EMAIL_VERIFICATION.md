# HIGH 5 – Email verification

Passenger registration now requires ownership confirmation of the submitted email address. New registrations receive a signed verification link, valid for 24 hours, and cannot sign in until they confirm it. Existing accounts are marked verified by migration `0003_verify_existing_accounts` to avoid locking out users who signed up before this feature was deployed. Superusers created after the migration are marked verified automatically.

Run migrations before starting the application:

```powershell
python manage.py migrate
```

In development, the configured Django console email backend prints the verification message and link in the `runserver` terminal. For production, configure an authenticated email backend through environment variables, use HTTPS, and set the correct trusted host/domain. Do not commit provider credentials.

The verification link opens a confirmation page; the user must submit its confirmation form to verify. This avoids link-preview bots confirming accounts simply by fetching the URL. Resending uses a generic response and is throttled per email address and IP for 60 seconds.

Test the complete flow with:

```powershell
python manage.py test accounts
```

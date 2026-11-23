from django.db import migrations


def mark_existing_users_verified(apps, schema_editor):
    """Do not lock out accounts created before verification was introduced."""
    User = apps.get_model("accounts", "User")
    User.objects.all().update(email_verified=True)


def reverse_mark_existing_users(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.all().update(email_verified=False)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_user_email_verified")]

    operations = [migrations.RunPython(mark_existing_users_verified, reverse_mark_existing_users)]

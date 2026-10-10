from django.db import migrations


def mark_existing_verified(apps, schema_editor):
    # Accounts that existed before e-mail verification was introduced are not
    # locked out if verification is enabled later.
    User = apps.get_model("accounts", "User")
    User.objects.update(email_verified=True)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_ratelimit_and_email_verified")]

    operations = [migrations.RunPython(mark_existing_verified, migrations.RunPython.noop)]

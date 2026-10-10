"""Add or remove clearly marked demo users and votes.

    python manage.py demo_data add      # demo users + votes on existing polls
    python manage.py demo_data remove   # delete demo users (their votes go too)

Demo users have e-mails ending in @demo.invalid and an unusable password, so
nobody can log in as them and they are easy to find and delete before launch.
Real users and real votes are never touched.
"""

import random

from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from polls.models import Poll, Vote

DEMO_DOMAIN = "demo.invalid"
DEMO_USERNAMES = ["ayse_k", "mehmet.y", "zeynep", "can_demir", "elif", "deniz_a", "burak", "selin.t"]
VOTE_PROBABILITY = 0.75


class Command(BaseCommand):
    help = "Add or remove demo users and votes (e-mails end with @" + DEMO_DOMAIN + ")."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["add", "remove"])

    def handle(self, *args, action, **options):
        if action == "add":
            self.add()
        else:
            self.remove()

    def demo_users(self):
        return User.objects.filter(email__endswith="@" + DEMO_DOMAIN)

    def add(self):
        users = []
        for name in DEMO_USERNAMES:
            email = f"demo-{name.replace('.', '-').replace('_', '-')}@{DEMO_DOMAIN}"
            user = User.objects.filter(email=email).first()
            if user is None:
                if User.objects.filter(username__iexact=name).exists():
                    raise CommandError(f"Kullanıcı adı zaten kullanılıyor: {name}")
                user = User(email=email, username=name)
                user.set_unusable_password()
                user.save()
            users.append(user)

        rng = random.Random(42)  # same result on every run
        created = 0
        for poll in Poll.objects.prefetch_related("options"):
            options = list(poll.options.all())
            weights = [rng.random() + 0.2 for _ in options]
            for user in users:
                if rng.random() > VOTE_PROBABILITY:
                    continue
                _, was_created = Vote.objects.get_or_create(
                    user=user, poll=poll, defaults={"option": rng.choices(options, weights)[0]}
                )
                created += was_created
        self.stdout.write(f"{len(users)} demo kullanıcı hazır, {created} yeni oy eklendi.")

    def remove(self):
        users = self.demo_users()
        count = users.count()
        users.delete()
        self.stdout.write(f"{count} demo kullanıcı ve oyları silindi.")

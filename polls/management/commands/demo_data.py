"""Add or remove clearly marked demo users, sample polls and votes.

    python manage.py demo_data add      # demo users + sample polls + votes
    python manage.py demo_data remove   # delete demo users (their polls and votes go too)

Demo users have e-mails ending in @demo.invalid and an unusable password, so
nobody can log in as them and they are easy to find and delete before launch.
Real users and real votes are never touched. Removing a demo user also deletes
the polls that user authored (and their votes), so avoid keeping real data on them.
"""

import random

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from polls.models import Option, Poll, Vote

DEMO_DOMAIN = "demo.invalid"
DEMO_USERNAMES = ["ayse_k", "mehmet.y", "zeynep", "can_demir", "elif", "deniz_a", "burak", "selin.t"]
VOTE_PROBABILITY = 0.75

# (author, question, description, options): authored by demo users so the feed
# does not look like a single person wrote everything.
SAMPLE_POLLS = [
    ("ayse_k", "Hafta sonu ne yapsam?", "Hava güzel olacak, evde oturmak da cazip.",
     ["Piknik", "Sinema", "Evde dizi maratonu", "Arkadaşlarla buluşma"]),
    ("mehmet.y", "Kahve mi çay mı?", "", ["Kahve", "Çay"]),
    ("can_demir", "Yeni telefon: iPhone mu Android mi?", "Bütçem aynı, kararsız kaldım.",
     ["iPhone", "Android", "Eskisiyle devam"]),
    ("zeynep", "Tatil için hangisi?", "Yaz geliyor, bir seçim yapmam lazım.",
     ["Kapadokya", "Ege kıyıları", "Karadeniz yaylaları", "Yurt dışı", "Evde kal"]),
    ("elif", "Bu hafta spora başlasam mı?", "", ["Evet, başla", "Haftaya", "Boşver"]),
]


class Command(BaseCommand):
    help = "Add or remove demo users, sample polls and votes (e-mails end with @" + DEMO_DOMAIN + ")."

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
        users = {}
        for name in DEMO_USERNAMES:
            email = f"demo-{name.replace('.', '-').replace('_', '-')}@{DEMO_DOMAIN}"
            user = User.objects.filter(email=email).first()
            if user is None:
                if User.objects.filter(username__iexact=name).exists():
                    raise CommandError(f"Kullanıcı adı zaten kullanılıyor: {name}")
                user = User(email=email, username=name)
                user.set_unusable_password()
                user.save()
            users[name] = user

        polls_created = 0
        for author, question, description, options in SAMPLE_POLLS:
            if Poll.objects.filter(author=users[author], question=question).exists():
                continue
            with transaction.atomic():
                poll = Poll.objects.create(author=users[author], question=question, description=description)
                Option.objects.bulk_create(
                    [Option(poll=poll, text=text, order=index) for index, text in enumerate(options)]
                )
            polls_created += 1

        rng = random.Random(42)  # same result on every run
        votes_created = 0
        for poll in Poll.objects.prefetch_related("options").order_by("id"):
            options = list(poll.options.all())
            weights = [rng.random() + 0.2 for _ in options]
            for user in users.values():
                if rng.random() > VOTE_PROBABILITY:
                    continue
                _, was_created = Vote.objects.get_or_create(
                    user=user, poll=poll, defaults={"option": rng.choices(options, weights)[0]}
                )
                votes_created += was_created
        self.stdout.write(
            f"{len(users)} demo kullanıcı hazır, {polls_created} yeni örnek anket, {votes_created} yeni oy eklendi."
        )

    def remove(self):
        users = self.demo_users()
        count = users.count()
        users.delete()
        self.stdout.write(f"{count} demo kullanıcı, açtıkları anketler ve oyları silindi.")

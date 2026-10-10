from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from accounts.models import User

from .models import Option, Poll, Vote


class DemoDataTests(TestCase):
    def setUp(self):
        self.real = User.objects.create_user(email="gercek@example.com", username="gercek", password="Sifre-Cok-Guclu-2026")
        self.poll = Poll.objects.create(author=self.real, question="Soru?")
        Option.objects.bulk_create([Option(poll=self.poll, text="A", order=0), Option(poll=self.poll, text="B", order=1)])
        self.real_vote = Vote.objects.create(user=self.real, poll=self.poll, option=self.poll.options.first())

    def run_command(self, action):
        call_command("demo_data", action, stdout=StringIO())

    def demo_users(self):
        return User.objects.filter(email__endswith="@demo.invalid")

    def test_add_creates_unusable_demo_users_and_votes(self):
        self.run_command("add")
        self.assertEqual(self.demo_users().count(), 8)
        self.assertTrue(all(not u.has_usable_password() for u in self.demo_users()))
        self.assertGreater(Vote.objects.exclude(user=self.real).count(), 0)

    def test_add_is_idempotent(self):
        self.run_command("add")
        users, votes = self.demo_users().count(), Vote.objects.count()
        self.run_command("add")
        self.assertEqual((self.demo_users().count(), Vote.objects.count()), (users, votes))

    def test_remove_deletes_only_demo_data(self):
        self.run_command("add")
        self.run_command("remove")
        self.assertFalse(self.demo_users().exists())
        self.assertEqual(list(User.objects.all()), [self.real])
        self.assertEqual(list(Vote.objects.all()), [self.real_vote])
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

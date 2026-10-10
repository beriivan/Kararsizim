from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from .models import Option, Poll, Vote

PASSWORD = "Sifre-Cok-Guclu-2026"


def make_user(name="ahmet"):
    return User.objects.create_user(email=f"{name}@example.com", username=name, password=PASSWORD)


def make_poll(author, closes_at=None, question="Soru?", options=("Sinema", "Restoran")):
    poll = Poll.objects.create(author=author, question=question, closes_at=closes_at)
    Option.objects.bulk_create([Option(poll=poll, text=t, order=i) for i, t in enumerate(options)])
    return poll


class CreateWithDurationTests(TestCase):
    url = reverse("poll_create")

    def setUp(self):
        self.client.force_login(make_user())

    def create(self, **extra):
        return self.client.post(self.url, {"question": "Soru?", "option": ["A", "B"], **extra})

    def test_form_offers_the_durations(self):
        html = self.client.get(self.url).content.decode()
        for label in ["Süresiz", "1 saat", "24 saat", "3 gün", "7 gün"]:
            self.assertIn(label, html)

    def test_default_is_no_deadline(self):
        self.create()
        self.assertIsNone(Poll.objects.get().closes_at)

    def test_chosen_duration_sets_closing_time(self):
        before = timezone.now()
        self.create(duration="24h")
        closes = Poll.objects.get().closes_at
        self.assertAlmostEqual((closes - before).total_seconds(), 24 * 3600, delta=30)

    def test_each_choice_maps_to_its_length(self):
        for key, hours in {"1h": 1, "3d": 72, "7d": 168}.items():
            Poll.objects.all().delete()
            self.create(duration=key, submission_token="")
            closes = Poll.objects.get().closes_at
            self.assertAlmostEqual((closes - timezone.now()).total_seconds(), hours * 3600, delta=30, msg=key)

    def test_unknown_duration_is_rejected(self):
        response = self.create(duration="1000y")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Poll.objects.exists())


class ClosedPollTests(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.voter = make_user("zeynep")
        self.open_poll = make_poll(self.owner, closes_at=timezone.now() + timedelta(hours=2), question="Açık")
        self.closed_poll = make_poll(self.owner, closes_at=timezone.now() - timedelta(minutes=1), question="Kapalı")

    def test_is_closed_property(self):
        self.assertFalse(self.open_poll.is_closed)
        self.assertTrue(self.closed_poll.is_closed)
        self.assertFalse(make_poll(self.owner).is_closed)  # no deadline

    def test_voting_on_a_closed_poll_is_rejected(self):
        self.client.force_login(self.voter)
        option = self.closed_poll.options.first()
        response = self.client.post(reverse("vote", args=[self.closed_poll.pk]), {"option": option.pk}, follow=True)
        self.assertContains(response, "süresi doldu")
        self.assertFalse(Vote.objects.exists())

    def test_voting_on_an_open_poll_with_deadline_works(self):
        self.client.force_login(self.voter)
        option = self.open_poll.options.first()
        self.client.post(reverse("vote", args=[self.open_poll.pk]), {"option": option.pk})
        self.assertEqual(Vote.objects.count(), 1)

    def test_changing_a_vote_after_closing_is_rejected(self):
        poll = make_poll(self.owner, closes_at=timezone.now() + timedelta(hours=1))
        first, second = poll.options.all()
        Vote.objects.create(user=self.voter, poll=poll, option=first)
        Poll.objects.filter(pk=poll.pk).update(closes_at=timezone.now() - timedelta(seconds=1))
        self.client.force_login(self.voter)
        self.client.post(reverse("vote", args=[poll.pk]), {"option": second.pk})
        self.assertEqual(Vote.objects.get().option, first)

    def test_closed_detail_shows_winner_and_hides_the_vote_form(self):
        a, b = self.closed_poll.options.all()
        Vote.objects.create(user=self.voter, poll=self.closed_poll, option=b)
        response = self.client.get(reverse("poll_detail", args=[self.closed_poll.pk]))
        self.assertContains(response, "Karar verildi")
        self.assertContains(response, "Kazanan: <b>Restoran</b>")
        self.assertNotContains(response, "Oyumu ver")
        self.assertNotContains(response, 'name="option"')
        self.assertContains(response, "Sonuçlar · 1 oy")  # results stay visible

    def test_closed_detail_with_a_tie_and_with_no_votes(self):
        a, b = self.closed_poll.options.all()
        self.assertContains(self.client.get(reverse("poll_detail", args=[self.closed_poll.pk])), "kimse oy vermedi")
        Vote.objects.create(user=self.voter, poll=self.closed_poll, option=a)
        Vote.objects.create(user=self.owner, poll=self.closed_poll, option=b)
        response = self.client.get(reverse("poll_detail", args=[self.closed_poll.pk]))
        self.assertContains(response, "Berabere")

    def test_open_detail_shows_the_countdown_and_the_form(self):
        response = self.client.get(reverse("poll_detail", args=[self.open_poll.pk]))
        self.assertContains(response, "Oylamanın bitmesine")
        self.assertContains(response, "Oyumu ver")
        self.assertNotContains(response, "Karar verildi")

    def test_feed_badges(self):
        response = self.client.get(reverse("home"))
        html = response.content.decode()
        self.assertEqual(html.count("🏁 Karar verildi"), 1)
        self.assertEqual(html.count("⏳"), 1)

    def test_poll_without_deadline_has_no_badge_or_countdown(self):
        Poll.objects.all().delete()
        poll = make_poll(self.owner)
        html = self.client.get(reverse("poll_detail", args=[poll.pk])).content.decode()
        self.assertNotIn("Oylamanın bitmesine", html)
        self.assertNotIn("Karar verildi", html)

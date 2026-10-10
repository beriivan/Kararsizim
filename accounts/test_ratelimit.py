from django.test import TestCase
from django.urls import reverse

from polls.models import Option, Poll, Vote

from . import views as account_views
from .models import RateLimitEvent, User
from .ratelimit import allow

PASSWORD = "Sifre-Cok-Guclu-2026"


class AllowTests(TestCase):
    def test_blocks_after_limit_and_counts_per_key(self):
        self.assertTrue(allow("k1", 2, 60))
        self.assertTrue(allow("k1", 2, 60))
        self.assertFalse(allow("k1", 2, 60))
        self.assertTrue(allow("k2", 2, 60))  # other keys are independent

    def test_old_events_do_not_count(self):
        from datetime import timedelta

        from django.utils import timezone

        allow("k", 1, 60)
        RateLimitEvent.objects.update(created_at=timezone.now() - timedelta(seconds=120))
        self.assertTrue(allow("k", 1, 60))


class LoginRateLimitTests(TestCase):
    def setUp(self):
        User.objects.create_user(email="ahmet@example.com", username="ahmet", password=PASSWORD)
        self.url = reverse("login")

    def attempt(self, email="ahmet@example.com", password="yanlis", **extra):
        return self.client.post(self.url, {"username": email, "password": password}, **extra)

    def test_repeated_wrong_passwords_get_429_then_even_correct_password_is_blocked(self):
        for _ in range(account_views.LOGIN_EMAIL_LIMIT):
            self.assertEqual(self.attempt().status_code, 200)
        blocked = self.attempt()
        self.assertEqual(blocked.status_code, 429)
        self.assertContains(blocked, "Çok hızlı gidiyorsun", status_code=429)
        self.assertIn("Retry-After", blocked)
        self.assertEqual(self.attempt(password=PASSWORD).status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_other_emails_are_not_blocked_by_one_targeted_account(self):
        for _ in range(account_views.LOGIN_EMAIL_LIMIT + 1):
            self.attempt()
        User.objects.create_user(email="zeynep@example.com", username="zeynep", password=PASSWORD)
        self.assertEqual(self.attempt(email="zeynep@example.com", password=PASSWORD).status_code, 302)

    def test_get_requests_are_never_counted(self):
        for _ in range(account_views.LOGIN_IP_LIMIT + 5):
            self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_ip_limit_applies_across_many_emails(self):
        for i in range(account_views.LOGIN_IP_LIMIT):
            self.attempt(email=f"kisi{i}@example.com")
        self.assertEqual(self.attempt(email="baska@example.com").status_code, 429)

    def test_ip_comes_from_forwarded_header(self):
        for i in range(account_views.LOGIN_IP_LIMIT):
            self.attempt(email=f"kisi{i}@example.com", HTTP_X_FORWARDED_FOR="1.1.1.1, 10.0.0.1")
        self.assertEqual(
            self.attempt(email="x@example.com", HTTP_X_FORWARDED_FOR="1.1.1.1").status_code, 429
        )
        self.assertEqual(
            self.attempt(email="x@example.com", HTTP_X_FORWARDED_FOR="2.2.2.2").status_code, 200
        )


class RegisterRateLimitTests(TestCase):
    def test_register_is_limited_per_ip(self):
        url = reverse("register")
        for i in range(account_views.REGISTER_LIMIT):
            self.client.post(url, {"username": f"kisi{i}", "email": f"k{i}@example.com", "password1": "a", "password2": "b"})
        self.assertEqual(self.client.post(url, {}).status_code, 429)
        self.assertEqual(self.client.get(url).status_code, 200)  # only POSTs are counted


class PollActionRateLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="ahmet@example.com", username="ahmet", password=PASSWORD)
        self.client.force_login(self.user)

    def test_poll_creation_is_limited_per_user(self):
        from polls import views as poll_views

        url = reverse("poll_create")
        for i in range(poll_views.POLL_CREATE_LIMIT):
            self.client.post(url, {"question": f"Soru {i}", "option": ["A", "B"]})
        self.assertEqual(Poll.objects.count(), poll_views.POLL_CREATE_LIMIT)
        self.assertEqual(self.client.post(url, {"question": "Fazla", "option": ["A", "B"]}).status_code, 429)
        self.assertEqual(Poll.objects.count(), poll_views.POLL_CREATE_LIMIT)

    def test_other_users_are_not_affected(self):
        from polls import views as poll_views

        url = reverse("poll_create")
        for i in range(poll_views.POLL_CREATE_LIMIT + 1):
            self.client.post(url, {"question": f"Soru {i}", "option": ["A", "B"]})
        other = User.objects.create_user(email="b@example.com", username="zeynep", password=PASSWORD)
        self.client.force_login(other)
        self.assertEqual(self.client.post(url, {"question": "Benim", "option": ["A", "B"]}).status_code, 302)

    def test_voting_is_limited_per_user(self):
        from polls import views as poll_views

        poll = Poll.objects.create(author=self.user, question="Soru?")
        Option.objects.bulk_create([Option(poll=poll, text="A", order=0), Option(poll=poll, text="B", order=1)])
        option = poll.options.first()
        url = reverse("vote", args=[poll.pk])
        for _ in range(poll_views.VOTE_LIMIT):
            self.assertEqual(self.client.post(url, {"option": option.pk}).status_code, 302)
        self.assertEqual(self.client.post(url, {"option": option.pk}).status_code, 429)
        self.assertEqual(Vote.objects.count(), 1)


class AdminLoginRateLimitTests(TestCase):
    def test_admin_login_is_throttled_per_ip(self):
        url = "/admin/login/"
        data = {"username": "x@example.com", "password": "yanlis"}
        for _ in range(account_views.ADMIN_LOGIN_LIMIT):
            self.assertEqual(self.client.post(url, data).status_code, 200)
        self.assertEqual(self.client.post(url, data).status_code, 429)
        self.assertEqual(self.client.get(url).status_code, 200)  # viewing the form is free

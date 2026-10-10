import re
from unittest import mock

from django.core import mail, signing
from django.test import TestCase, override_settings
from django.urls import reverse

from polls.models import Option, Poll, Vote

from . import emails
from . import views as account_views
from .models import User

PASSWORD = "Sifre-Cok-Guclu-2026"
NEW_PASSWORD = "Yepyeni-Sifre-9137"


def make_user(name="ahmet", verified=False, **extra):
    return User.objects.create_user(
        email=f"{name}@example.com", username=name, password=PASSWORD, email_verified=verified, **extra
    )


def link_in(message):
    return re.search(r"https?://\S+", message.body).group(0)


@override_settings(EMAIL_ENABLED=True)
class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def request_reset(self, email="ahmet@example.com"):
        return self.client.post(reverse("password_reset"), {"email": email})

    def test_page_renders(self):
        self.assertContains(self.client.get(reverse("password_reset")), "Şifreni sıfırla")

    def test_existing_account_gets_one_mail_with_a_link(self):
        response = self.request_reset()
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ahmet@example.com"])
        self.assertIn("/sifre-sifirla/", link_in(mail.outbox[0]))
        self.assertIn("@ahmet", mail.outbox[0].body)

    def test_unknown_address_looks_identical_and_sends_nothing(self):
        response = self.request_reset("yok@example.com")
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_email_match_is_case_insensitive(self):
        self.request_reset("AHMET@Example.com")
        self.assertEqual(len(mail.outbox), 1)

    def test_accounts_without_a_password_get_no_mail(self):
        demo = User(email="demo-x@demo.invalid", username="demo_x")
        demo.set_unusable_password()
        demo.save()
        self.request_reset("demo-x@demo.invalid")
        self.assertEqual(len(mail.outbox), 0)

    def test_full_flow_sets_new_password_and_verifies_email(self):
        self.request_reset()
        confirm = self.client.get(link_in(mail.outbox[0]), follow=True)
        self.assertContains(confirm, "Yeni şifreni belirle")
        form_url = confirm.redirect_chain[-1][0]
        done = self.client.post(form_url, {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD})
        self.assertRedirects(done, reverse("password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertTrue(self.user.email_verified)
        self.client.logout()
        login = self.client.post(reverse("login"), {"username": "ahmet@example.com", "password": NEW_PASSWORD})
        self.assertEqual(login.status_code, 302)

    def test_link_can_be_used_only_once(self):
        self.request_reset()
        link = link_in(mail.outbox[0])
        form_url = self.client.get(link, follow=True).redirect_chain[-1][0]
        self.client.post(form_url, {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD})
        self.client.logout()
        self.assertContains(self.client.get(link, follow=True), "Bağlantı geçersiz")

    def test_garbage_link_is_rejected(self):
        response = self.client.get(reverse("password_reset_confirm", args=["xx", "yyy-zzz"]))
        self.assertContains(response, "Bağlantı geçersiz")

    def test_reset_requests_are_rate_limited(self):
        for _ in range(account_views.PASSWORD_RESET_LIMIT):
            self.assertEqual(self.request_reset().status_code, 302)
        self.assertEqual(self.request_reset().status_code, 429)

    def test_login_page_links_to_reset(self):
        self.assertContains(self.client.get(reverse("login")), reverse("password_reset"))


class FeatureIsHiddenWithoutEmailTests(TestCase):
    @override_settings(EMAIL_ENABLED=False)
    def test_pages_404_and_link_hidden(self):
        for name, args in [("password_reset", []), ("password_reset_done", []), ("password_reset_complete", [])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 404, name)
        self.assertEqual(self.client.get(reverse("verify_email", args=["x"])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("login")), "Şifreni mi unuttun?")

    @override_settings(EMAIL_ENABLED=False)
    def test_registration_sends_nothing_and_shows_no_banner(self):
        self.client.post(
            reverse("register"),
            {"username": "yeni", "email": "yeni@example.com", "password1": PASSWORD, "password2": PASSWORD},
        )
        self.assertEqual(len(mail.outbox), 0)
        self.assertNotContains(self.client.get(reverse("home")), "doğrulamadın")


@override_settings(EMAIL_ENABLED=True)
class VerificationTests(TestCase):
    def register(self, name="yeni"):
        return self.client.post(
            reverse("register"),
            {"username": name, "email": f"{name}@example.com", "password1": PASSWORD, "password2": PASSWORD},
        )

    def test_registration_sends_a_verification_mail_and_still_succeeds(self):
        response = self.register()
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["yeni@example.com"])
        self.assertFalse(User.objects.get(username="yeni").email_verified)

    def test_registration_survives_a_mail_outage(self):
        with mock.patch("accounts.emails.send_mail", side_effect=OSError("smtp down")):
            response = self.register()
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(username="yeni").exists())

    def test_link_verifies_the_account(self):
        self.register()
        user = User.objects.get(username="yeni")
        self.client.logout()  # the link works without being logged in
        response = self.client.get(link_in(mail.outbox[0]), follow=True)
        self.assertContains(response, "doğrulandı")
        user.refresh_from_db()
        self.assertTrue(user.email_verified)

    def test_bad_expired_and_stale_tokens_are_rejected(self):
        user = make_user("ahmet")
        for token in ["bozuk", emails.make_token(user)[:-3] + "xyz"]:
            self.assertContains(self.client.get(reverse("verify_email", args=[token]), follow=True), "geçersiz")
        # a link made for an old address stops working once the address changed
        old = emails.make_token(user)
        User.objects.filter(pk=user.pk).update(email="degisti@example.com")
        self.assertContains(self.client.get(reverse("verify_email", args=[old]), follow=True), "geçersiz")
        # expired
        with mock.patch.object(emails, "MAX_AGE", -1):
            self.assertIsNone(emails.read_token(emails.make_token(user)))
        user.refresh_from_db()
        self.assertFalse(user.email_verified)

    def test_token_cannot_be_forged_for_another_user(self):
        victim = make_user("kurban")
        forged = signing.dumps({"u": victim.pk, "e": victim.email}, salt="baska-tuz")
        self.client.get(reverse("verify_email", args=[forged]))
        victim.refresh_from_db()
        self.assertFalse(victim.email_verified)

    def test_banner_only_for_unverified_logged_in_users(self):
        self.assertNotContains(self.client.get(reverse("home")), "doğrulamadın")
        user = make_user("ahmet")
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse("home")), "E-postanı henüz doğrulamadın")
        User.objects.filter(pk=user.pk).update(email_verified=True)
        self.assertNotContains(self.client.get(reverse("home")), "doğrulamadın")

    def test_resend_sends_a_mail_and_is_rate_limited(self):
        self.client.force_login(make_user("ahmet"))
        url = reverse("resend_verification")
        self.assertEqual(self.client.get(url).status_code, 405)
        for _ in range(account_views.RESEND_LIMIT):
            self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(len(mail.outbox), account_views.RESEND_LIMIT)
        self.assertEqual(self.client.post(url).status_code, 429)

    def test_resend_requires_login_and_ignores_verified_users(self):
        url = reverse("resend_verification")
        self.assertEqual(self.client.post(url).status_code, 302)  # to login
        self.assertEqual(len(mail.outbox), 0)
        self.client.force_login(make_user("ahmet", verified=True))
        self.client.post(url)
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_does_not_redirect_to_other_sites(self):
        self.client.force_login(make_user("ahmet"))
        response = self.client.post(reverse("resend_verification"), {"next": "//kotu.example.com/"})
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        response = self.client.post(reverse("resend_verification"), {"next": "/anket/yeni/"})
        self.assertRedirects(response, "/anket/yeni/", fetch_redirect_response=False)

    def test_verification_mail_never_leaks_into_pages(self):
        self.register()
        html = self.client.get(reverse("home")).content.decode()
        self.assertNotIn("yeni@example.com", html)


@override_settings(EMAIL_ENABLED=True, REQUIRE_VERIFIED_EMAIL=True)
class EnforcementTests(TestCase):
    def setUp(self):
        self.owner = make_user("sahip", verified=True)
        self.poll = Poll.objects.create(author=self.owner, question="Soru?")
        Option.objects.bulk_create([Option(poll=self.poll, text="A", order=0), Option(poll=self.poll, text="B", order=1)])

    def test_unverified_cannot_create_polls(self):
        self.client.force_login(make_user("ahmet"))
        response = self.client.post(reverse("poll_create"), {"question": "Yeni?", "option": ["A", "B"]}, follow=True)
        self.assertContains(response, "önce e-postanı doğrulaman gerekiyor")
        self.assertEqual(Poll.objects.count(), 1)

    def test_unverified_cannot_vote(self):
        self.client.force_login(make_user("ahmet"))
        option = self.poll.options.first()
        self.client.post(reverse("vote", args=[self.poll.pk]), {"option": option.pk})
        self.assertFalse(Vote.objects.exists())

    def test_verified_users_can_do_both(self):
        self.client.force_login(make_user("zeynep", verified=True))
        self.client.post(reverse("poll_create"), {"question": "Yeni?", "option": ["A", "B"]})
        self.assertEqual(Poll.objects.count(), 2)
        self.client.post(reverse("vote", args=[self.poll.pk]), {"option": self.poll.options.first().pk})
        self.assertEqual(Vote.objects.count(), 1)

    def test_visitors_can_still_browse(self):
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)
        self.assertEqual(self.client.get(reverse("poll_detail", args=[self.poll.pk])).status_code, 200)

    @override_settings(REQUIRE_VERIFIED_EMAIL=False)
    def test_enforcement_is_off_by_default(self):
        self.client.force_login(make_user("ahmet"))
        self.client.post(reverse("poll_create"), {"question": "Yeni?", "option": ["A", "B"]})
        self.assertEqual(Poll.objects.count(), 2)

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import User


class UserModelTests(TestCase):
    def test_create_user_normalizes_email_to_lowercase(self):
        user = User.objects.create_user(email="  Ahmet@Example.COM ", username="ahmet", password="x-pass-123")
        self.assertEqual(user.email, "ahmet@example.com")
        self.assertTrue(user.check_password("x-pass-123"))
        self.assertFalse(user.is_staff)

    def test_create_superuser(self):
        admin = User.objects.create_superuser(email="admin@example.com", username="admin", password="x-pass-123")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_login_field_is_email(self):
        self.assertEqual(User.USERNAME_FIELD, "email")

    def test_duplicate_email_differing_in_case_is_rejected(self):
        User.objects.create_user(email="a@example.com", username="first", password="x-pass-123")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(email="A@Example.com", username="second", password="x-pass-123")

    def test_duplicate_username_differing_in_case_is_rejected(self):
        User.objects.create_user(email="a@example.com", username="Ahmet", password="x-pass-123")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(email="b@example.com", username="ahmet", password="x-pass-123")

    def test_username_validation(self):
        for bad in ["ab", "has space", "türkçe", "a" * 31, "emoji😀"]:
            user = User(email="x@example.com", username=bad)
            with self.assertRaises(ValidationError, msg=bad) as ctx:
                user.full_clean(exclude=["password"])
            self.assertIn("username", ctx.exception.message_dict, bad)

    def test_valid_usernames(self):
        for good in ["abc", "Ahmet_01", "a.b.c", "a" * 30]:
            user = User(email="x@example.com", username=good)
            user.full_clean(exclude=["password"])


STRONG_PASSWORD = "Sifre-Cok-Guclu-2026"


class RegisterTests(TestCase):
    url = reverse("register")

    def post(self, **overrides):
        data = {
            "username": "ahmet",
            "email": "ahmet@example.com",
            "password1": STRONG_PASSWORD,
            "password2": STRONG_PASSWORD,
        }
        data.update(overrides)
        return self.client.post(self.url, data)

    def test_page_renders_for_visitor(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_valid_registration_creates_user_logs_in_and_welcomes(self):
        response = self.post(email="Ahmet@Example.com")
        # Don't fetch the redirect here, that would consume the flash message.
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        user = User.objects.get(username="ahmet")
        self.assertEqual(user.email, "ahmet@example.com")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertContains(self.client.get(reverse("home")), "Hoş geldin @ahmet!")

    def test_duplicate_email_is_rejected_even_with_different_case(self):
        User.objects.create_user(email="ahmet@example.com", username="first", password=STRONG_PASSWORD)
        response = self.post(username="second", email="AHMET@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bu e-posta adresi zaten kayıtlı.")
        self.assertEqual(User.objects.count(), 1)

    def test_duplicate_username_is_rejected_even_with_different_case(self):
        User.objects.create_user(email="a@example.com", username="Ahmet", password=STRONG_PASSWORD)
        response = self.post(username="ahmet", email="b@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bu kullanıcı adı zaten alınmış.")
        self.assertEqual(User.objects.count(), 1)

    def test_invalid_username_is_rejected(self):
        response = self.post(username="a b")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_password_mismatch_is_rejected(self):
        response = self.post(password2="baska-bir-parola-123")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_weak_password_is_rejected(self):
        response = self.post(password1="12345678", password2="12345678")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_logged_in_user_is_redirected_away(self):
        self.post()
        self.assertRedirects(self.client.get(self.url), reverse("home"))


class LoginLogoutTests(TestCase):
    login_url = reverse("login")

    def setUp(self):
        self.user = User.objects.create_user(
            email="ahmet@example.com", username="ahmet", password=STRONG_PASSWORD
        )

    def login(self, email="ahmet@example.com", password=STRONG_PASSWORD, **extra):
        return self.client.post(self.login_url, {"username": email, "password": password, **extra})

    def test_login_with_email_works(self):
        response = self.login()
        self.assertRedirects(response, reverse("home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_login_email_is_case_insensitive(self):
        self.login(email="  AHMET@Example.COM ")
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_with_username_does_not_work(self):
        response = self.login(email="ahmet")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_wrong_password_fails_with_turkish_message(self):
        response = self.login(password="yanlis-parola")
        self.assertContains(response, "E-posta veya parola hatalı.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_next_parameter_is_respected(self):
        response = self.login(next="/admin/")
        self.assertRedirects(response, "/admin/", fetch_redirect_response=False)

    def test_unsafe_next_parameter_is_ignored(self):
        response = self.login(next="https://evil.example.com/")
        self.assertRedirects(response, reverse("home"))

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_via_post_logs_out(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_navbar_changes_with_login_state(self):
        visitor = self.client.get(reverse("home"))
        self.assertContains(visitor, "Giriş yap")
        self.assertContains(visitor, "Kayıt ol")
        self.client.force_login(self.user)
        member = self.client.get(reverse("home"))
        self.assertContains(member, "@ahmet")
        self.assertContains(member, "Çıkış")
        self.assertNotContains(member, "Kayıt ol")

    def test_email_is_never_rendered(self):
        self.client.force_login(self.user)
        for url in [reverse("home"), reverse("login"), reverse("register")]:
            self.assertNotContains(self.client.get(url, follow=True), "ahmet@example.com")

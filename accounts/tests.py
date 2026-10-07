from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

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

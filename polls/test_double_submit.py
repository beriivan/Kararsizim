import re
import uuid
from unittest import mock

from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .models import Poll

PASSWORD = "Sifre-Cok-Guclu-2026"


class DoubleSubmitTests(TestCase):
    url = reverse("poll_create")

    def setUp(self):
        self.user = User.objects.create_user(email="ahmet@example.com", username="ahmet", password=PASSWORD)
        self.client.force_login(self.user)

    def payload(self, token, **extra):
        data = {"question": "Bu akşam ne yapsam?", "description": "", "option": ["Sinema", "Restoran"]}
        if token is not None:
            data["submission_token"] = str(token)
        data.update(extra)
        return data

    def test_form_is_rendered_with_a_fresh_token(self):
        first = self.client.get(self.url).content.decode()
        second = self.client.get(self.url).content.decode()
        token = re.compile(r'name="submission_token" value="([0-9a-f-]{36})"')
        self.assertTrue(token.search(first))
        self.assertNotEqual(token.search(first).group(1), token.search(second).group(1))

    def test_submitting_the_same_form_five_times_creates_one_poll(self):
        token = uuid.uuid4()
        responses = [self.client.post(self.url, self.payload(token)) for _ in range(5)]
        poll = Poll.objects.get()  # exactly one
        for response in responses:
            self.assertRedirects(response, reverse("poll_detail", args=[poll.pk]), fetch_redirect_response=False)
        self.assertEqual(poll.options.count(), 2)

    def test_repeat_submission_tells_the_user_it_already_exists(self):
        token = uuid.uuid4()
        self.client.post(self.url, self.payload(token))
        response = self.client.post(self.url, self.payload(token), follow=True)
        self.assertContains(response, "Bu anket zaten yayında")
        self.assertEqual(Poll.objects.count(), 1)

    def test_different_forms_create_different_polls(self):
        self.client.post(self.url, self.payload(uuid.uuid4()))
        self.client.post(self.url, self.payload(uuid.uuid4()))
        self.assertEqual(Poll.objects.count(), 2)

    def test_invalid_submission_does_not_burn_the_token(self):
        token = uuid.uuid4()
        bad = self.client.post(self.url, self.payload(token, option=["tek"]))
        self.assertEqual(bad.status_code, 200)
        self.assertContains(bad, str(token))  # same token is kept in the re-rendered form
        self.assertFalse(Poll.objects.exists())
        self.client.post(self.url, self.payload(token))
        self.assertEqual(Poll.objects.count(), 1)

    def test_missing_or_garbage_token_still_works(self):
        self.client.post(self.url, self.payload(None))
        self.client.post(self.url, self.payload("kötü-kod", question="İkinci"))
        self.assertEqual(Poll.objects.count(), 2)

    def test_someone_elses_token_is_ignored_not_leaked(self):
        token = uuid.uuid4()
        other = User.objects.create_user(email="b@example.com", username="zeynep", password=PASSWORD)
        theirs = Poll.objects.create(author=other, question="Onun anketi", submission_token=token)
        response = self.client.post(self.url, self.payload(token))
        mine = Poll.objects.exclude(pk=theirs.pk).get()
        self.assertEqual(mine.author, self.user)
        self.assertRedirects(response, reverse("poll_detail", args=[mine.pk]), fetch_redirect_response=False)
        theirs.refresh_from_db()
        self.assertEqual(theirs.question, "Onun anketi")

    def test_database_rejects_a_second_poll_with_the_same_token(self):
        token = uuid.uuid4()
        Poll.objects.create(author=self.user, question="a", submission_token=token)
        from django.db import transaction

        with self.assertRaises(IntegrityError), transaction.atomic():
            Poll.objects.create(author=self.user, question="b", submission_token=token)

    def test_race_between_two_identical_requests_creates_one_poll(self):
        """Both requests pass the 'already exists' check; the unique token lets one win."""
        token = uuid.uuid4()
        real_filter = Poll.objects.filter
        calls = {"n": 0}

        def blind_first_lookup(*args, **kwargs):
            # The very first lookup (the "does it exist already?" pre-check) sees nothing,
            # as it would if the other request had not committed yet.
            calls["n"] += 1
            if calls["n"] == 1:
                return Poll.objects.none()
            return real_filter(*args, **kwargs)

        self.client.post(self.url, self.payload(token))  # the "other" request wins first
        with mock.patch.object(Poll.objects, "filter", side_effect=blind_first_lookup):
            response = self.client.post(self.url, self.payload(token))
        poll = Poll.objects.get()
        self.assertRedirects(response, reverse("poll_detail", args=[poll.pk]), fetch_redirect_response=False)

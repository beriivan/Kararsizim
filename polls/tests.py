from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .models import Option, Poll

PASSWORD = "Sifre-Cok-Guclu-2026"


def make_user(name="ahmet"):
    return User.objects.create_user(email=f"{name}@example.com", username=name, password=PASSWORD)


def make_poll(author, question="Bu akşam ne yapsam?", options=("Sinema", "Restoran")):
    poll = Poll.objects.create(author=author, question=question)
    Option.objects.bulk_create([Option(poll=poll, text=text, order=i) for i, text in enumerate(options)])
    return poll


class PollCreateTests(TestCase):
    url = reverse("poll_create")

    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def post(self, options, **extra):
        data = {"question": "Bu akşam ne yapsam?", "description": "", "option": options, **extra}
        return self.client.post(self.url, data)

    def test_visitor_is_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('login')}?next={self.url}")

    def test_visitor_cannot_create_poll(self):
        self.client.logout()
        self.client.post(self.url, {"question": "x", "option": ["a", "b"]})
        self.assertFalse(Poll.objects.exists())

    def test_form_renders_for_member(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="option"', count=5)

    def test_valid_poll_with_two_options(self):
        response = self.post(["Sinema", "Restoran"])
        poll = Poll.objects.get()
        self.assertRedirects(response, reverse("poll_detail", args=[poll.pk]))
        self.assertEqual(poll.author, self.user)
        self.assertEqual([o.text for o in poll.options.all()], ["Sinema", "Restoran"])

    def test_valid_poll_with_five_options_keeps_order_and_skips_blanks(self):
        self.post(["A", "", "B", "  ", "C", "D", "E"])
        poll = Poll.objects.get()
        self.assertEqual([o.text for o in poll.options.all()], ["A", "B", "C", "D", "E"])

    def test_one_option_is_rejected(self):
        response = self.post(["Sinema", "", ""])
        self.assertContains(response, "En az 2 seçenek girmelisin.")
        self.assertFalse(Poll.objects.exists())

    def test_six_options_are_rejected(self):
        response = self.post(["1", "2", "3", "4", "5", "6"])
        self.assertContains(response, "En fazla 5 seçenek ekleyebilirsin.")
        self.assertFalse(Poll.objects.exists())
        self.assertFalse(Option.objects.exists())

    def test_duplicate_options_are_rejected_ignoring_case_and_spaces(self):
        response = self.post(["Sinema", "  sinema "])
        self.assertContains(response, "Aynı seçeneği birden fazla kez ekleyemezsin.")
        self.assertFalse(Poll.objects.exists())

    def test_too_long_option_is_rejected(self):
        response = self.post(["a" * 81, "b"])
        self.assertContains(response, "en fazla 80 karakter")
        self.assertFalse(Poll.objects.exists())

    def test_question_is_required_and_limited(self):
        self.assertEqual(self.post(["a", "b"], question="").status_code, 200)
        self.assertEqual(self.post(["a", "b"], question="q" * 151).status_code, 200)
        self.assertFalse(Poll.objects.exists())

    def test_description_limit(self):
        self.assertEqual(self.post(["a", "b"], description="d" * 501).status_code, 200)
        self.assertFalse(Poll.objects.exists())

    def test_invalid_submission_keeps_entered_values(self):
        response = self.post(["Sinema", ""], question="Soru burada")
        self.assertContains(response, 'value="Sinema"')
        self.assertContains(response, "Soru burada")


class PollViewTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.poll = make_poll(self.user)

    def test_visitor_sees_feed(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Bu akşam ne yapsam?")
        self.assertContains(response, "@ahmet")
        self.assertContains(response, "Sinema")

    def test_feed_empty_state(self):
        Poll.objects.all().delete()
        self.assertContains(self.client.get(reverse("home")), "Henüz kimse kararsız değil")

    def test_feed_is_newest_first_and_paginated(self):
        for i in range(25):
            make_poll(self.user, question=f"Soru {i}")
        first = self.client.get(reverse("home"))
        self.assertEqual(len(first.context["page"]), 20)
        self.assertEqual(first.context["page"][0].question, "Soru 24")
        second = self.client.get(reverse("home"), {"sayfa": 2})
        self.assertEqual(len(second.context["page"]), 6)
        self.assertEqual(self.client.get(reverse("home"), {"sayfa": "abc"}).status_code, 200)

    def test_feed_does_not_run_a_query_per_poll(self):
        for i in range(10):
            make_poll(self.user, question=f"Soru {i}")
        with self.assertNumQueries(3):  # count + polls + options (author is joined)
            self.client.get(reverse("home"))

    def test_visitor_sees_detail(self):
        response = self.client.get(reverse("poll_detail", args=[self.poll.pk]))
        self.assertContains(response, "Bu akşam ne yapsam?")
        self.assertContains(response, "Restoran")
        self.assertNotContains(response, "Sil")

    def test_detail_404(self):
        self.assertEqual(self.client.get(reverse("poll_detail", args=[9999])).status_code, 404)

    def test_owner_sees_delete_link_but_others_do_not(self):
        url = reverse("poll_detail", args=[self.poll.pk])
        self.client.force_login(make_user("zeynep"))
        self.assertNotContains(self.client.get(url), reverse("poll_delete", args=[self.poll.pk]))
        self.client.force_login(self.user)
        self.assertContains(self.client.get(url), reverse("poll_delete", args=[self.poll.pk]))

    def test_profile_lists_only_that_users_polls(self):
        other = make_user("zeynep")
        make_poll(other, question="Zeynep'in sorusu")
        response = self.client.get(reverse("user_profile", args=["AHMET"]))
        self.assertContains(response, "Bu akşam ne yapsam?")
        self.assertNotContains(response, "Zeynep'in sorusu")
        self.assertContains(response, "1 anket")

    def test_profile_404_for_unknown_user(self):
        self.assertEqual(self.client.get(reverse("user_profile", args=["yok"])).status_code, 404)


class PollDeleteTests(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.other = make_user("zeynep")
        self.poll = make_poll(self.owner)
        self.url = reverse("poll_delete", args=[self.poll.pk])

    def test_visitor_is_redirected_to_login_and_nothing_is_deleted(self):
        self.assertRedirects(self.client.post(self.url), f"{reverse('login')}?next={self.url}")
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_owner_sees_confirmation_page(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.url), "Evet, sil")
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_owner_can_delete_with_post(self):
        self.client.force_login(self.owner)
        self.assertRedirects(self.client.post(self.url), reverse("home"))
        self.assertFalse(Poll.objects.exists())
        self.assertFalse(Option.objects.exists())

    def test_other_member_cannot_delete(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())


class PollPrivacyTests(TestCase):
    def test_email_is_not_rendered_on_feed_detail_profile_or_form(self):
        user = make_user()
        poll = make_poll(user)
        self.client.force_login(user)
        urls = [
            reverse("home"),
            reverse("poll_detail", args=[poll.pk]),
            reverse("user_profile", args=[user.username]),
            reverse("poll_create"),
            reverse("poll_delete", args=[poll.pk]),
        ]
        for url in urls:
            self.assertNotContains(self.client.get(url), "ahmet@example.com", msg_prefix=url)
        self.client.logout()
        for url in urls[:3]:
            self.assertNotContains(self.client.get(url), "ahmet@example.com", msg_prefix=url)

    def test_user_content_is_escaped(self):
        user = make_user()
        make_poll(user, question="<script>alert(1)</script>")
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")

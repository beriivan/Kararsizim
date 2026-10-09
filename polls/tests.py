from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import User

from .models import Option, Poll, Vote

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


def vote_url(poll):
    return reverse("vote", args=[poll.pk])


class VoteTests(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.voter = make_user("zeynep")
        self.poll = make_poll(self.owner)
        self.sinema, self.restoran = self.poll.options.all()

    def cast(self, option):
        return self.client.post(vote_url(self.poll), {"option": option.pk})

    def test_visitor_is_sent_to_login_and_back_to_the_poll(self):
        detail = reverse("poll_detail", args=[self.poll.pk])
        response = self.cast(self.sinema)
        self.assertRedirects(response, f"{reverse('login')}?next={detail}", fetch_redirect_response=False)
        self.assertFalse(Vote.objects.exists())
        follow = self.client.get(response.url)
        self.assertContains(follow, "Oy vermek için önce giriş yapmalısın.")

    def test_login_after_vote_attempt_returns_to_the_poll(self):
        detail = reverse("poll_detail", args=[self.poll.pk])
        self.cast(self.sinema)
        response = self.client.post(
            reverse("login"), {"username": "zeynep@example.com", "password": PASSWORD, "next": detail}
        )
        self.assertRedirects(response, detail)

    def test_vote_requires_post(self):
        self.client.force_login(self.voter)
        self.assertEqual(self.client.get(vote_url(self.poll)).status_code, 405)

    def test_first_vote_is_created_with_message(self):
        self.client.force_login(self.voter)
        response = self.cast(self.sinema)
        self.assertRedirects(response, reverse("poll_detail", args=[self.poll.pk]), fetch_redirect_response=False)
        vote = Vote.objects.get()
        self.assertEqual((vote.user, vote.poll, vote.option), (self.voter, self.poll, self.sinema))
        self.assertContains(self.client.get(response.url), "Oyun kaydedildi, sağ ol! 💜")

    def test_second_vote_updates_instead_of_adding(self):
        self.client.force_login(self.voter)
        self.cast(self.sinema)
        self.cast(self.restoran)
        vote = Vote.objects.get()  # still exactly one
        self.assertEqual(vote.option, self.restoran)
        self.assertEqual(self.client.get(reverse("poll_detail", args=[self.poll.pk])).context["poll"].total_votes, 1)

    def test_owner_can_vote_on_own_poll(self):
        self.client.force_login(self.owner)
        self.cast(self.sinema)
        self.assertEqual(Vote.objects.get().user, self.owner)

    def test_option_of_another_poll_is_rejected(self):
        other_poll = make_poll(self.owner, question="Başka anket", options=("X", "Y"))
        foreign = other_poll.options.first()
        self.client.force_login(self.voter)
        response = self.cast(foreign)
        self.assertRedirects(response, reverse("poll_detail", args=[self.poll.pk]), fetch_redirect_response=False)
        self.assertFalse(Vote.objects.exists())

    def test_missing_or_invalid_option_is_rejected(self):
        self.client.force_login(self.voter)
        for payload in [{}, {"option": ""}, {"option": "abc"}, {"option": "-1"}, {"option": "9" * 40}, {"option": "9999"}]:
            response = self.client.post(vote_url(self.poll), payload)
            self.assertEqual(response.status_code, 302, payload)
        self.assertFalse(Vote.objects.exists())

    def test_vote_on_missing_poll_is_404(self):
        self.client.force_login(self.voter)
        self.assertEqual(self.client.post(reverse("vote", args=[9999]), {"option": 1}).status_code, 404)

    def test_database_enforces_one_vote_per_user_per_poll(self):
        Vote.objects.create(user=self.voter, poll=self.poll, option=self.sinema)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Vote.objects.create(user=self.voter, poll=self.poll, option=self.restoran)

    def test_deleting_a_poll_deletes_its_votes(self):
        Vote.objects.create(user=self.voter, poll=self.poll, option=self.sinema)
        self.poll.delete()
        self.assertFalse(Vote.objects.exists())


class ResultsTests(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.poll = make_poll(self.owner, options=("Sinema", "Restoran", "Evde kal"))
        self.sinema, self.restoran, self.evde = self.poll.options.all()
        self.voters = [make_user(f"kisi{i}") for i in range(4)]
        for voter, option in zip(self.voters, [self.sinema, self.sinema, self.sinema, self.restoran]):
            Vote.objects.create(user=voter, poll=self.poll, option=option)

    def detail(self):
        return self.client.get(reverse("poll_detail", args=[self.poll.pk]))

    def test_results_are_visible_to_visitors(self):
        response = self.detail()
        self.assertContains(response, "Sonuçlar · 4 oy")
        results = {o.text: (o.vote_count, o.percent) for o in response.context["poll"].option_results}
        self.assertEqual(results, {"Sinema": (3, 75), "Restoran": (1, 25), "Evde kal": (0, 0)})

    def test_only_the_leading_option_is_highlighted(self):
        winners = [o.text for o in self.detail().context["poll"].option_results if o.is_winner]
        self.assertEqual(winners, ["Sinema"])
        self.assertContains(self.detail(), "👑 Sinema")

    def test_ties_highlight_all_leaders_and_no_votes_highlight_none(self):
        Vote.objects.filter(user=self.voters[0]).update(option=self.restoran)  # 2 - 2
        winners = {o.text for o in self.detail().context["poll"].option_results if o.is_winner}
        self.assertEqual(winners, {"Sinema", "Restoran"})
        Vote.objects.all().delete()
        self.assertFalse(any(o.is_winner for o in self.detail().context["poll"].option_results))

    def test_voter_usernames_are_listed_under_their_option(self):
        by_text = {o.text: [u.username for u in o.voters] for o in self.detail().context["poll"].option_results}
        self.assertEqual(by_text, {"Sinema": ["kisi0", "kisi1", "kisi2"], "Restoran": ["kisi3"], "Evde kal": []})
        self.assertContains(self.detail(), "@kisi3")

    def test_current_vote_is_preselected_and_button_says_update(self):
        self.client.force_login(self.voters[3])
        response = self.detail()
        self.assertEqual(response.context["user_option_id"], self.restoran.pk)
        self.assertContains(response, "Oyumu güncelle")
        self.client.force_login(self.owner)
        self.assertContains(self.detail(), "Oyumu ver")

    def test_options_keep_their_order(self):
        texts = [o.text for o in self.detail().context["poll"].option_results]
        self.assertEqual(texts, ["Sinema", "Restoran", "Evde kal"])

    def test_detail_query_count_does_not_grow_with_votes(self):
        with CaptureQueriesContext(connection) as before:
            self.detail()
        for i in range(10):
            Vote.objects.create(user=make_user(f"extra{i}"), poll=self.poll, option=self.evde)
        with CaptureQueriesContext(connection) as after:
            self.detail()
        self.assertEqual(len(before), len(after))


class FeedVoteTests(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.quiet = make_poll(self.owner, question="Sessiz anket")
        self.popular = make_poll(self.owner, question="Popüler anket")
        self.newest = make_poll(self.owner, question="En yeni anket")
        for i in range(3):
            Vote.objects.create(user=make_user(f"v{i}"), poll=self.popular, option=self.popular.options.first())
        Vote.objects.create(user=User.objects.get(username="v0"), poll=self.newest, option=self.newest.options.first())

    def questions(self, **params):
        return [p.question for p in self.client.get(reverse("home"), params).context["page"]]

    def test_default_order_is_newest_first(self):
        self.assertEqual(self.questions(), ["En yeni anket", "Popüler anket", "Sessiz anket"])

    def test_most_voted_order(self):
        self.assertEqual(self.questions(sirala="populer"), ["Popüler anket", "En yeni anket", "Sessiz anket"])

    def test_unknown_sort_falls_back_to_newest(self):
        self.assertEqual(self.questions(sirala="bozuk"), ["En yeni anket", "Popüler anket", "Sessiz anket"])

    def test_pagination_links_keep_the_sort(self):
        for i in range(21):
            make_poll(self.owner, question=f"Ek {i}")
        response = self.client.get(reverse("home"), {"sirala": "populer"})
        self.assertContains(response, "?sayfa=2&amp;sirala=populer")

    def test_cards_show_total_votes_and_mini_results(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "3 oy")
        self.assertContains(response, "%100")

    def test_voted_badge_only_for_polls_the_user_voted_on(self):
        self.client.force_login(User.objects.get(username="v0"))
        response = self.client.get(reverse("home"))
        flags = {p.question: p.user_voted for p in response.context["page"]}
        self.assertEqual(flags, {"En yeni anket": True, "Popüler anket": True, "Sessiz anket": False})
        self.assertContains(response, "✓ Oy verdin", count=2)

    def test_visitor_sees_no_voted_badge(self):
        self.assertNotContains(self.client.get(reverse("home")), "✓ Oy verdin")

    def test_feed_query_count_does_not_grow_with_polls_or_votes(self):
        self.client.force_login(User.objects.get(username="v0"))
        with CaptureQueriesContext(connection) as before:
            self.client.get(reverse("home"))
        for i in range(8):
            poll = make_poll(self.owner, question=f"Çok {i}", options=("A", "B", "C", "D", "E"))
            Vote.objects.create(user=User.objects.get(username="v1"), poll=poll, option=poll.options.first())
        with CaptureQueriesContext(connection) as after:
            self.client.get(reverse("home"))
        self.assertEqual(len(before), len(after))


class VotePrivacyTests(TestCase):
    def test_voter_email_is_never_rendered(self):
        owner = make_user()
        voter = make_user("zeynep")
        poll = make_poll(owner)
        Vote.objects.create(user=voter, poll=poll, option=poll.options.first())
        urls = [
            reverse("home"),
            reverse("home") + "?sirala=populer",
            reverse("poll_detail", args=[poll.pk]),
            reverse("user_profile", args=[owner.username]),
            reverse("user_profile", args=[voter.username]),
        ]
        for client_user in (None, owner, voter):
            if client_user:
                self.client.force_login(client_user)
            for url in urls:
                response = self.client.get(url)
                for email in ("ahmet@example.com", "zeynep@example.com"):
                    self.assertNotContains(response, email, msg_prefix=url)

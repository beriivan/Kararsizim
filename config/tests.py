from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.views.defaults import server_error

from accounts.models import User
from polls.models import Option, Poll


def make_poll(author):
    poll = Poll.objects.create(author=author, question="Soru?")
    Option.objects.bulk_create([Option(poll=poll, text="A", order=0), Option(poll=poll, text="B", order=1)])
    return poll


class ErrorPageTests(TestCase):
    def test_unknown_url_renders_branded_404(self):
        response = self.client.get("/boyle-bir-sayfa-yok/")
        self.assertContains(response, "Bu sayfa kararsız kalıp kaybolmuş", status_code=404)
        self.assertContains(response, "Ana sayfaya dön", status_code=404)

    def test_missing_poll_renders_branded_404(self):
        response = self.client.get(reverse("poll_detail", args=[12345]))
        self.assertContains(response, "404", status_code=404)

    def test_forbidden_delete_renders_branded_403(self):
        owner = User.objects.create_user(email="a@example.com", username="owner", password="Sifre-Cok-Guclu-2026")
        other = User.objects.create_user(email="b@example.com", username="other", password="Sifre-Cok-Guclu-2026")
        poll = make_poll(owner)
        self.client.force_login(other)
        response = self.client.post(reverse("poll_delete", args=[poll.pk]))
        self.assertContains(response, "Buna iznin yok", status_code=403)
        self.assertTrue(Poll.objects.filter(pk=poll.pk).exists())

    def test_500_page_is_standalone_and_branded(self):
        response = server_error(RequestFactory().get("/"))
        self.assertEqual(response.status_code, 500)
        self.assertIn("Bir şeyler ters gitti", response.content.decode())


class LayoutTests(TestCase):
    def test_base_layout_has_favicon_font_script_and_skip_link(self):
        html = self.client.get(reverse("home")).content.decode()
        self.assertIn("img/favicon.svg", html)
        self.assertIn("Plus+Jakarta+Sans", html)
        self.assertIn("js/main.js", html)
        self.assertIn('class="skip-link"', html)
        self.assertIn('id="content"', html)

    def test_messages_are_announced_to_screen_readers(self):
        user = User.objects.create_user(email="a@example.com", username="owner", password="Sifre-Cok-Guclu-2026")
        self.client.force_login(user)
        self.client.post(
            reverse("poll_create"), {"question": "Soru?", "option": ["A", "B"]}, follow=False
        )
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'role="status"')
        self.assertContains(response, "Anketin yayında!")

    def test_login_notice_is_not_duplicated_next_to_a_message(self):
        owner = User.objects.create_user(email="a@example.com", username="owner", password="Sifre-Cok-Guclu-2026")
        poll = make_poll(owner)
        response = self.client.post(reverse("vote", args=[poll.pk]), {"option": poll.options.first().pk}, follow=True)
        self.assertContains(response, "Oy vermek için önce giriş yapmalısın.")
        self.assertNotContains(response, "Devam etmek için önce giriş yapmalısın.")

    def test_login_notice_shows_when_redirected_without_a_message(self):
        response = self.client.get(reverse("poll_create"), follow=True)
        self.assertContains(response, "Devam etmek için önce giriş yapmalısın.")

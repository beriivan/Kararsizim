import re

from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .models import Option, Poll, Vote


class ShareTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="gizli@example.com", username="ahmet", password="Sifre-Cok-Guclu-2026")
        self.poll = Poll.objects.create(author=self.owner, question='Kahve mi "çay" mı? <b>')
        Option.objects.bulk_create(
            [Option(poll=self.poll, text="Kahve", order=0), Option(poll=self.poll, text="Çay", order=1)]
        )
        Vote.objects.create(user=self.owner, poll=self.poll, option=self.poll.options.first())
        self.url = reverse("poll_detail", args=[self.poll.pk])

    def meta(self, html):
        return dict(re.findall(r'<meta (?:property|name)="([^"]+)" content="([^"]*)"', html))

    def test_detail_has_open_graph_tags_with_absolute_urls(self):
        html = self.client.get(self.url).content.decode()
        meta = self.meta(html)
        self.assertEqual(meta["og:type"], "article")
        self.assertEqual(meta["og:url"], "http://testserver" + self.url)
        self.assertEqual(meta["og:image"], "http://testserver/static/img/og-image.png")
        self.assertEqual(meta["twitter:card"], "summary_large_image")
        self.assertIn("Kahve / Çay · 1 oy", meta["og:description"])
        self.assertIn(f'<link rel="canonical" href="http://testserver{self.url}">', html)

    def test_question_in_meta_is_escaped(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn('og:title" content="Kahve mi &quot;çay&quot; mı? &lt;b&gt;"', html)

    def test_share_block_has_the_link(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn('id="share-url"', html)
        self.assertIn(f'value="http://testserver{self.url}"', html)
        self.assertIn("data-copy", html)

    def test_other_pages_have_default_site_meta(self):
        meta = self.meta(self.client.get(reverse("home")).content.decode())
        self.assertEqual(meta["og:type"], "website")
        self.assertEqual(meta["og:title"], "Kararsızım")
        self.assertTrue(meta["og:image"].endswith("/static/img/og-image.png"))

    def test_no_email_in_share_markup(self):
        self.assertNotContains(self.client.get(self.url), "gizli@example.com")

    def test_preview_image_is_a_real_png_served_statically(self):
        response = self.client.get("/static/img/og-image.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertTrue(b"".join(response.streaming_content).startswith(b"\x89PNG"))

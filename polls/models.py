from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import models
from django.utils import timezone


class Poll(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="polls", verbose_name="yazar"
    )
    question = models.CharField("soru", max_length=150)
    description = models.TextField(
        "açıklama", blank=True, validators=[MaxLengthValidator(500, "Açıklama en fazla 500 karakter olabilir.")]
    )
    created_at = models.DateTimeField("oluşturulma tarihi", auto_now_add=True)
    # One-time code issued with the create form; the unique constraint makes a
    # double click / resubmit create the poll only once.
    submission_token = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    # When set, voting ends at this moment and the poll is "decided" ("Karar verildi").
    closes_at = models.DateTimeField("bitiş zamanı", null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "anket"
        verbose_name_plural = "anketler"

    @property
    def is_closed(self):
        return self.closes_at is not None and self.closes_at <= timezone.now()

    def __str__(self):
        return self.question


class Option(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="options", verbose_name="anket")
    text = models.CharField("metin", max_length=80)
    order = models.PositiveSmallIntegerField("sıra", default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "seçenek"
        verbose_name_plural = "seçenekler"

    def __str__(self):
        return self.text


class Vote(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="votes", verbose_name="kullanıcı"
    )
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="votes", verbose_name="anket")
    option = models.ForeignKey(Option, on_delete=models.CASCADE, related_name="votes", verbose_name="seçenek")
    created_at = models.DateTimeField("oluşturulma tarihi", auto_now_add=True)
    updated_at = models.DateTimeField("güncellenme tarihi", auto_now=True)

    class Meta:
        constraints = [
            # One vote per user per poll; changing a vote updates this row.
            models.UniqueConstraint(fields=["user", "poll"], name="polls_vote_one_per_user_per_poll"),
        ]
        verbose_name = "oy"
        verbose_name_plural = "oylar"

    def __str__(self):
        return f"{self.user} → {self.option}"

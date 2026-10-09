from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import models


class Poll(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="polls", verbose_name="yazar"
    )
    question = models.CharField("soru", max_length=150)
    description = models.TextField(
        "açıklama", blank=True, validators=[MaxLengthValidator(500, "Açıklama en fazla 500 karakter olabilir.")]
    )
    created_at = models.DateTimeField("oluşturulma tarihi", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "anket"
        verbose_name_plural = "anketler"

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

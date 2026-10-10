import uuid

from django import forms
from django.db import IntegrityError, transaction

from .models import Option, Poll

MIN_OPTIONS = 2
MAX_OPTIONS = 5
OPTION_MAX_LENGTH = Option._meta.get_field("text").max_length


class PollForm(forms.ModelForm):
    """Poll + 2-5 options.

    Options arrive as repeated `option` inputs (read straight from the POST data)
    so the rules also hold when JavaScript is disabled.
    """

    description = forms.CharField(
        label="Açıklama (isteğe bağlı)",
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    submission_token = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Poll
        fields = ("question", "description")
        labels = {"question": "Sorun ne?"}
        widgets = {"question": forms.TextInput(attrs={"placeholder": "Bu akşam ne yapsam?"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cleaned_options = []

    @property
    def option_values(self):
        """Values to re-render in the option inputs (always at least MAX_OPTIONS rows)."""
        submitted = self.data.getlist("option") if self.is_bound else []
        return submitted + [""] * (MAX_OPTIONS - len(submitted))

    def clean_submission_token(self):
        # A missing or malformed code is not the user's fault: just ignore it.
        try:
            return uuid.UUID(self.cleaned_data.get("submission_token", ""))
        except (ValueError, AttributeError, TypeError):
            return None

    def clean(self):
        cleaned = super().clean()
        options = [text.strip() for text in self.data.getlist("option") if text.strip()]
        errors = []

        if len(options) < MIN_OPTIONS:
            errors.append(f"En az {MIN_OPTIONS} seçenek girmelisin.")
        if len(options) > MAX_OPTIONS:
            errors.append(f"En fazla {MAX_OPTIONS} seçenek ekleyebilirsin.")
        if any(len(text) > OPTION_MAX_LENGTH for text in options):
            errors.append(f"Her seçenek en fazla {OPTION_MAX_LENGTH} karakter olabilir.")
        if len({text.casefold() for text in options}) != len(options):
            errors.append("Aynı seçeneği birden fazla kez ekleyemezsin.")

        if errors:
            raise forms.ValidationError(errors)
        self.cleaned_options = options
        return cleaned

    def save(self, author):
        """Create the poll and its options together or not at all.

        Returns `(poll, created)`. Submitting the same form twice (double click,
        reload, back button) returns the poll created the first time.
        """
        token = self.cleaned_data.get("submission_token")
        if token:
            existing = Poll.objects.filter(submission_token=token).first()
            if existing and existing.author_id == author.pk:
                return existing, False
            if existing:  # someone else's code: ignore it
                token = None

        try:
            with transaction.atomic():
                poll = super().save(commit=False)
                poll.author = author
                poll.submission_token = token
                poll.save()
                Option.objects.bulk_create(
                    [Option(poll=poll, text=text, order=index) for index, text in enumerate(self.cleaned_options)]
                )
        except IntegrityError:
            # Two identical requests raced; the unique token let only one win.
            existing = Poll.objects.filter(submission_token=token, author=author).first() if token else None
            if existing is None:
                raise
            return existing, False
        return poll, True

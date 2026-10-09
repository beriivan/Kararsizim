from django import forms
from django.db import transaction

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
        """Create the poll and its options together or not at all."""
        with transaction.atomic():
            poll = super().save(commit=False)
            poll.author = author
            poll.save()
            Option.objects.bulk_create(
                [Option(poll=poll, text=text, order=index) for index, text in enumerate(self.cleaned_options)]
            )
        return poll

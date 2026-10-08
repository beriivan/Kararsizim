from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


class RegisterForm(UserCreationForm):
    """Sign-up form: username, e-mail and password (twice)."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Kullanıcı adı"
        self.fields["username"].help_text = "3–30 karakter; harf, rakam, _ ve . kullanabilirsin."
        self.fields["email"].label = "E-posta"
        self.fields["email"].help_text = "Giriş için kullanılır, kimseye gösterilmez."
        self.fields["password1"].label = "Parola"
        self.fields["password2"].label = "Parola (tekrar)"
        self.fields["password2"].help_text = ""
        self.fields["username"].widget.attrs.update({"autocomplete": "username"})
        self.fields["email"].widget.attrs.update({"autocomplete": "email"})

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"])
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Bu e-posta adresi zaten kayıtlı.", code="unique")
        return email


class LoginForm(AuthenticationForm):
    """Log in with e-mail + password. The field keeps the name `username`."""

    error_messages = {
        "invalid_login": "E-posta veya parola hatalı.",
        "inactive": "Bu hesap aktif değil.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "E-posta"
        self.fields["username"].widget = forms.EmailInput(
            attrs={"autofocus": True, "autocomplete": "email"}
        )
        self.fields["password"].label = "Parola"

    def clean_username(self):
        # E-mails are stored lower-cased, so match case-insensitively.
        return User.objects.normalize_email(self.cleaned_data["username"])

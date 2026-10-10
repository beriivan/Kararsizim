import hashlib

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetConfirmView, PasswordResetView
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .emails import read_token, send_verification_email
from .forms import LoginForm, RegisterForm
from .models import User
from .ratelimit import allow, client_ip, is_blocked, rate_limit, record, refund, too_many_requests

# Abuse limits (attempts per window).
REGISTER_LIMIT, REGISTER_WINDOW = 10, 60 * 60        # per IP, per hour
LOGIN_IP_LIMIT, LOGIN_IP_WINDOW = 20, 10 * 60        # per IP, per 10 minutes
LOGIN_EMAIL_LIMIT, LOGIN_EMAIL_WINDOW = 8, 10 * 60   # failed attempts per (IP, e-mail), per 10 minutes
ADMIN_LOGIN_LIMIT, ADMIN_LOGIN_WINDOW = 10, 10 * 60  # per IP, per 10 minutes (/admin/login/)


@rate_limit("register", REGISTER_LIMIT, REGISTER_WINDOW)
def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Hoş geldin @{user.username}!")
            if settings.EMAIL_ENABLED:
                if send_verification_email(request, user):
                    messages.info(request, "E-postana bir doğrulama bağlantısı gönderdik.")
                else:
                    messages.warning(
                        request,
                        "Doğrulama e-postasını şu an gönderemedik. Biraz sonra sayfanın üstündeki "
                        "uyarıdan yeniden gönderebilirsin.",
                    )
            return redirect("home")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})


class CustomLoginView(LoginView):
    form_class = LoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        # Throttle all attempts per IP, and *failed* attempts per (IP, e-mail).
        # Keying failures by IP too means a stranger cannot lock the real owner
        # out of an account just by guessing wrong passwords for its address.
        ip = client_ip(request)
        email = User.objects.normalize_email(request.POST.get("username", ""))[:120]
        fail_key = "login:fail:" + hashlib.sha256(f"{ip}|{email}".encode()).hexdigest()[:40]
        if not allow(f"login:ip:{ip}", LOGIN_IP_LIMIT, LOGIN_IP_WINDOW) or is_blocked(
            fail_key, LOGIN_EMAIL_LIMIT, LOGIN_EMAIL_WINDOW
        ):
            return too_many_requests(request, LOGIN_EMAIL_WINDOW)
        response = super().post(request, *args, **kwargs)
        if response.status_code != 302:  # form re-rendered with an error
            record(fail_key)
        return response


# --- Password reset (Django's token machinery, Turkish pages) -----------------

PASSWORD_RESET_LIMIT, PASSWORD_RESET_WINDOW = 5, 60 * 60  # per IP, per hour
RESEND_LIMIT, RESEND_WINDOW = 3, 60 * 60                  # per user, per hour


def _require_email_enabled():
    if not settings.EMAIL_ENABLED:
        raise Http404


class PasswordReset(PasswordResetView):
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/password_reset_email.txt"
    subject_template_name = "accounts/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")

    def dispatch(self, request, *args, **kwargs):
        _require_email_enabled()
        return super().dispatch(request, *args, **kwargs)


class PasswordResetConfirm(PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("password_reset_complete")

    def dispatch(self, request, *args, **kwargs):
        _require_email_enabled()
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        # Following the e-mailed link proves the user controls the address.
        user = form.user
        if not user.email_verified:
            user.email_verified = True
            user.save(update_fields=["email_verified"])
        return response


def password_reset_done(request):
    _require_email_enabled()
    return render(request, "accounts/password_reset_done.html")


def password_reset_complete(request):
    _require_email_enabled()
    return render(request, "accounts/password_reset_complete.html")


# --- E-mail verification ---------------------------------------------------------


def verify_email(request, token):
    _require_email_enabled()
    parsed = read_token(token)
    user = User.objects.filter(pk=parsed[0]).first() if parsed else None
    if user is None or user.email != parsed[1]:
        messages.error(request, "Bu doğrulama bağlantısı geçersiz ya da süresi dolmuş.")
        return redirect("home")
    if not user.email_verified:
        user.email_verified = True
        user.save(update_fields=["email_verified"])
    messages.success(request, "E-posta adresin doğrulandı, teşekkürler! 💜")
    return redirect("home")


@login_required
@require_POST
def resend_verification(request):
    _require_email_enabled()
    if request.user.email_verified:
        return redirect("home")
    key = f"resend:user:{request.user.pk}"
    if not allow(key, RESEND_LIMIT, RESEND_WINDOW):
        return too_many_requests(request, RESEND_WINDOW)
    if send_verification_email(request, request.user):
        messages.info(request, "Doğrulama bağlantısını yeniden gönderdik, gelen kutunu kontrol et.")
    else:
        refund(key)  # a failed send must not eat the user's hourly allowance
        messages.error(request, "E-postayı şu an gönderemedik, biraz sonra tekrar dene.")
    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = reverse("home")
    return redirect(next_url)

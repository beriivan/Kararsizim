from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .forms import LoginForm, RegisterForm
from .models import User
from .ratelimit import allow, client_ip, rate_limit, too_many_requests

# Abuse limits (attempts per window).
REGISTER_LIMIT, REGISTER_WINDOW = 10, 60 * 60        # per IP, per hour
LOGIN_IP_LIMIT, LOGIN_IP_WINDOW = 20, 10 * 60        # per IP, per 10 minutes
LOGIN_EMAIL_LIMIT, LOGIN_EMAIL_WINDOW = 8, 10 * 60   # per e-mail, per 10 minutes


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
            return redirect("home")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})


class CustomLoginView(LoginView):
    form_class = LoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        # Throttle by IP and by the e-mail being tried (slows password guessing).
        email = User.objects.normalize_email(request.POST.get("username", ""))[:120]
        ip_ok = allow(f"login:ip:{client_ip(request)}", LOGIN_IP_LIMIT, LOGIN_IP_WINDOW)
        email_ok = allow(f"login:email:{email}", LOGIN_EMAIL_LIMIT, LOGIN_EMAIL_WINDOW)
        if not (ip_ok and email_ok):
            return too_many_requests(request, LOGIN_EMAIL_WINDOW)
        return super().post(request, *args, **kwargs)

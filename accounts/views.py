from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .forms import LoginForm, RegisterForm


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

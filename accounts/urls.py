from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("kayit/", views.register, name="register"),
    path("giris/", views.CustomLoginView.as_view(), name="login"),
    # LogoutView only accepts POST.
    path("cikis/", LogoutView.as_view(), name="logout"),
]

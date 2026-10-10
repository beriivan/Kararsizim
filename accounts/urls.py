from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views
from .ratelimit import rate_limit

urlpatterns = [
    path("kayit/", views.register, name="register"),
    path("giris/", views.CustomLoginView.as_view(), name="login"),
    # LogoutView only accepts POST.
    path("cikis/", LogoutView.as_view(), name="logout"),
    # Password reset
    path(
        "sifre-sifirla/",
        rate_limit("password_reset", views.PASSWORD_RESET_LIMIT, views.PASSWORD_RESET_WINDOW)(
            views.PasswordReset.as_view()
        ),
        name="password_reset",
    ),
    path("sifre-sifirla/gonderildi/", views.password_reset_done, name="password_reset_done"),
    path("sifre-sifirla/tamam/", views.password_reset_complete, name="password_reset_complete"),
    path("sifre-sifirla/<uidb64>/<token>/", views.PasswordResetConfirm.as_view(), name="password_reset_confirm"),
    # E-mail verification
    path("e-posta-dogrula/tekrar/", views.resend_verification, name="resend_verification"),
    path("e-posta-dogrula/<str:token>/", views.verify_email, name="verify_email"),
]

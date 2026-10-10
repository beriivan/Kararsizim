from django.contrib import admin
from django.urls import include, path

from accounts.ratelimit import rate_limit
from accounts.views import ADMIN_LOGIN_LIMIT, ADMIN_LOGIN_WINDOW

# The admin has its own login view; throttle it like /giris/ (per IP).
admin.site.login = rate_limit("admin_login", ADMIN_LOGIN_LIMIT, ADMIN_LOGIN_WINDOW)(admin.site.login)

urlpatterns = [
    path("", include("polls.urls")),
    path("", include("accounts.urls")),
    path("admin/", admin.site.urls),
]

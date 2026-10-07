from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    # Placeholder home page; replaced by the poll feed in Phase 2.
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("admin/", admin.site.urls),
]

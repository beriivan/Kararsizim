from django.conf import settings


def features(request):
    """Expose feature flags to templates (read per request so tests can override them)."""
    return {
        "EMAIL_ENABLED": settings.EMAIL_ENABLED,
        "REQUIRE_VERIFIED_EMAIL": settings.REQUIRE_VERIFIED_EMAIL,
    }

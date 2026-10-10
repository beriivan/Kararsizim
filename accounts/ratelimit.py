"""Small database-backed rate limiter (fixed lookback window).

Counts are stored in `RateLimitEvent`, so they are shared between serverless
instances. A rare burst of simultaneous requests can slip a few extra attempts
through; that is fine for abuse protection.
"""

import random
from datetime import timedelta
from functools import wraps

from django.db import transaction
from django.shortcuts import render
from django.utils import timezone

from .models import RateLimitEvent

CLEANUP_PROBABILITY = 0.02
KEEP_EVENTS_FOR = timedelta(days=1)


def client_ip(request):
    """Client address; behind Vercel the proxy sets X-Forwarded-For."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def allow(key, limit, window_seconds):
    """Record one action for `key`; return False when the limit is already reached."""
    now = timezone.now()
    since = now - timedelta(seconds=window_seconds)
    with transaction.atomic():
        if RateLimitEvent.objects.filter(key=key, created_at__gte=since).count() >= limit:
            return False
        RateLimitEvent.objects.create(key=key)
    if random.random() < CLEANUP_PROBABILITY:
        RateLimitEvent.objects.filter(created_at__lt=now - KEEP_EVENTS_FOR).delete()
    return True


def refund(key):
    """Give back the most recent slot of `key` (the action did not really happen)."""
    last = RateLimitEvent.objects.filter(key=key).order_by("-created_at", "-id").first()
    if last is not None:
        last.delete()


def too_many_requests(request, retry_after):
    response = render(request, "429.html", {"retry_minutes": max(1, round(retry_after / 60))}, status=429)
    response["Retry-After"] = str(retry_after)
    return response


def rate_limit(scope, limit, window_seconds, by="ip", methods=("POST",)):
    """Limit a view. `by` is "ip" or "user" (falls back to the IP for visitors)."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method in methods:
                if by == "user" and request.user.is_authenticated:
                    who = f"user:{request.user.pk}"
                else:
                    who = f"ip:{client_ip(request)}"
                if not allow(f"{scope}:{who}", limit, window_seconds):
                    return too_many_requests(request, window_seconds)
            return view(request, *args, **kwargs)

        return wrapper

    return decorator

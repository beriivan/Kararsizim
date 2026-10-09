from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import PollForm
from .models import Poll

User = get_user_model()
POLLS_PER_PAGE = 20


def _poll_queryset():
    return Poll.objects.select_related("author").prefetch_related("options")


def _paginate(request, queryset):
    return Paginator(queryset, POLLS_PER_PAGE).get_page(request.GET.get("sayfa"))


def poll_list(request):
    page = _paginate(request, _poll_queryset())
    return render(request, "polls/poll_list.html", {"page": page})


@login_required
def poll_create(request):
    if request.method == "POST":
        form = PollForm(request.POST)
        if form.is_valid():
            poll = form.save(author=request.user)
            messages.success(request, "Anketin yayında!")
            return redirect("poll_detail", pk=poll.pk)
    else:
        form = PollForm()
    return render(request, "polls/poll_form.html", {"form": form})


def poll_detail(request, pk):
    poll = get_object_or_404(_poll_queryset(), pk=pk)
    return render(request, "polls/poll_detail.html", {"poll": poll})


@login_required
@require_http_methods(["GET", "POST"])
def poll_delete(request, pk):
    poll = get_object_or_404(Poll.objects.select_related("author"), pk=pk)
    if poll.author_id != request.user.pk:
        raise PermissionDenied
    if request.method == "POST":
        poll.delete()
        messages.success(request, "Anket silindi.")
        return redirect("home")
    return render(request, "polls/poll_confirm_delete.html", {"poll": poll})


def user_profile(request, username):
    profile_user = get_object_or_404(User, username__iexact=username)
    page = _paginate(request, _poll_queryset().filter(author=profile_user))
    return render(
        request,
        "polls/user_profile.html",
        {"profile_user": profile_user, "page": page, "poll_count": page.paginator.count},
    )

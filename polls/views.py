from collections import defaultdict

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from .forms import PollForm
from .models import Option, Poll, Vote

User = get_user_model()
POLLS_PER_PAGE = 20
OPTION_COLORS = 5  # options cycle through 5 colors (see main.css)

# NOTE: Django ignores Meta.ordering on aggregate (GROUP BY) queries, so every
# annotated queryset below sets its ordering explicitly.
SORT_ORDERINGS = {
    "yeni": ("-created_at", "-id"),
    "populer": ("-total_votes", "-created_at", "-id"),
}


def _poll_queryset(sort="yeni"):
    """Polls with author, total vote count and options (each with its vote count)."""
    options = Option.objects.annotate(vote_count=Count("votes")).order_by("order", "id")
    return (
        Poll.objects.select_related("author")
        .annotate(total_votes=Count("votes"))
        .prefetch_related(Prefetch("options", queryset=options))
        .order_by(*SORT_ORDERINGS[sort])
    )


def _decorate_poll(poll):
    """Attach `option_results` (percent, color, winner flag) to a poll."""
    options = list(poll.options.all())
    top = max((option.vote_count for option in options), default=0)
    for index, option in enumerate(options):
        option.percent = round(option.vote_count * 100 / poll.total_votes) if poll.total_votes else 0
        option.color = index % OPTION_COLORS
        option.is_winner = top > 0 and option.vote_count == top
    poll.option_results = options
    return poll


def _paginate(request, queryset):
    """Paginate and decorate the polls of the current page (results + "voted" flag)."""
    page = Paginator(queryset, POLLS_PER_PAGE).get_page(request.GET.get("sayfa"))
    voted_ids = set()
    if request.user.is_authenticated:
        voted_ids = set(
            Vote.objects.filter(user=request.user, poll__in=[p.pk for p in page]).values_list("poll_id", flat=True)
        )
    for poll in page:
        _decorate_poll(poll)
        poll.user_voted = poll.pk in voted_ids
    return page


def poll_list(request):
    sort = "populer" if request.GET.get("sirala") == "populer" else "yeni"
    page = _paginate(request, _poll_queryset(sort))
    return render(
        request,
        "polls/poll_list.html",
        {"page": page, "sort": sort, "page_extra": "&sirala=populer" if sort == "populer" else ""},
    )


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
    poll = _decorate_poll(get_object_or_404(_poll_queryset(), pk=pk))

    voters = defaultdict(list)
    user_option_id = None
    for vote in Vote.objects.filter(poll=poll).select_related("user").order_by("user__username"):
        voters[vote.option_id].append(vote.user)
        if request.user.is_authenticated and vote.user_id == request.user.pk:
            user_option_id = vote.option_id
    for option in poll.option_results:
        option.voters = voters[option.pk]

    return render(request, "polls/poll_detail.html", {"poll": poll, "user_option_id": user_option_id})


def _option_of_poll(poll, raw_id):
    """The option with this id *belonging to this poll*, or None."""
    if not raw_id or not raw_id.isdigit() or len(raw_id) > 18:
        return None
    return poll.options.filter(pk=int(raw_id)).first()


@require_POST
def vote(request, pk):
    poll = get_object_or_404(Poll, pk=pk)
    detail_url = reverse("poll_detail", args=[poll.pk])

    if not request.user.is_authenticated:
        messages.info(request, "Oy vermek için önce giriş yapmalısın.")
        return redirect_to_login(detail_url)

    option = _option_of_poll(poll, request.POST.get("option"))
    if option is None:
        messages.error(request, "Lütfen bu ankete ait bir seçenek seç.")
        return redirect(detail_url)

    Vote.objects.update_or_create(user=request.user, poll=poll, defaults={"option": option})
    messages.success(request, "Oyun kaydedildi, sağ ol! 💜")
    return redirect(detail_url)


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

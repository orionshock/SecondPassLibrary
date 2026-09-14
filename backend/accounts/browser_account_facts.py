from __future__ import annotations

from dataclasses import dataclass

from django.http import HttpRequest

from .models import UserProfile


_REQUEST_FACTS_ATTRIBUTE = "_second_pass_browser_account_facts"


@dataclass(frozen=True, slots=True)
class BrowserAccountFacts:
    user_id: int
    web_session_generation: int
    must_change_password: bool


def get_browser_account_facts(request: HttpRequest) -> BrowserAccountFacts | None:
    """Load fresh browser-account policy facts once for this request."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return None

    cached = getattr(request, _REQUEST_FACTS_ATTRIBUTE, None)
    if cached is not None and cached.user_id == user.pk:
        return cached

    values = UserProfile.objects.values(
        "user_id",
        "web_session_generation",
        "must_change_password",
    ).get(user_id=user.pk)
    facts = BrowserAccountFacts(**values)
    setattr(request, _REQUEST_FACTS_ATTRIBUTE, facts)
    return facts

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from django.http import HttpRequest

from .models import UserProfile


_REQUEST_ACTOR_ATTRIBUTE = "_second_pass_request_actor_context"


@dataclass(frozen=True, slots=True)
class RequestActorContext:
    user_id: int
    username: str
    first_name: str
    last_name: str
    profile_id: UUID
    role: str
    web_session_generation: int
    must_change_password: bool


class ActorRequest(Protocol):
    user: Any


def get_request_actor_context(
    request: HttpRequest | ActorRequest,
) -> RequestActorContext | None:
    """Load the current actor and owned account facts once for this request."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return None

    request_state_owner = getattr(request, "_request", request)
    cached = getattr(request_state_owner, _REQUEST_ACTOR_ATTRIBUTE, None)
    if cached is not None and cached.user_id == user.pk:
        return cached

    values = UserProfile.objects.values(
        "id",
        "role",
        "web_session_generation",
        "must_change_password",
    ).get(user_id=user.pk)
    actor = RequestActorContext(
        user_id=user.pk,
        username=user.get_username(),
        first_name=user.first_name or "",
        last_name=user.last_name or "",
        profile_id=values["id"],
        role=values["role"],
        web_session_generation=values["web_session_generation"],
        must_change_password=values["must_change_password"],
    )
    setattr(request_state_owner, _REQUEST_ACTOR_ATTRIBUTE, actor)
    return actor

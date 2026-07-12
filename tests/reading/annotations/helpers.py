from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model

from accounts.models import UserProfile
from library.models import BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from reading.models import Annotation, ReadingSession
from tests.utils.books import create_file_backed_book
from tests.utils.library_visibility import ensure_public_membership
from tests.utils.users import set_user_role


User = get_user_model()


def bookmark_payload(
    session: ReadingSession, value: str = "epubcfi(/6/2)"
) -> dict[str, Any]:
    return {
        "session": str(session.id),
        "kind": "bookmark",
        "selector": {"kind": "epub_cfi", "value": value},
    }


def highlight_payload(
    session: ReadingSession,
    *,
    value: str = "epubcfi(/6/2)",
    text: str = "hello",
    comment: str = "",
    color: str = "",
    quote: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "session": str(session.id),
        "kind": "highlight",
        "selector": {"kind": "epub_cfi", "value": value},
        "highlight_text": text,
    }
    if comment:
        payload["comment_text"] = comment
    if color:
        payload["highlight_color"] = color
    if quote is not None:
        payload["quote"] = quote
    return payload


class LostAccessAnnotationMixin:
    def _make_lost_access_session_with_annotation(self):
        user = User.objects.create_user(
            username="lostann", password="pass", email="lostann@example.com"
        )
        set_user_role(user, UserProfile.ROLE_READER)
        ensure_public_membership(user)
        group = LibraryGroup.objects.create(name="Lost Annotation Group")
        LibraryGroupMembership.objects.create(user=user, group=group)
        book = create_file_backed_book(
            title="Lost Annotation", assign_public=False
        ).book
        BookGroupAssignment.objects.create(book=book, group=group)
        session = ReadingSession.objects.create(user=user, book=book)
        annotation = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=book,
            selector_value="epubcfi(/6/2)",
            highlight_text="owned",
            highlight_color="yellow",
            comment_text="old",
        )
        LibraryGroupMembership.objects.filter(user=user, group=group).delete()
        return user, session, annotation

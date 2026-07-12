from __future__ import annotations

from django.contrib.auth import get_user_model

from tests.testenv.filesystem import IsolatedMediaRootMixin
from accounts.client_api import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession
from library.groups.services import add_book_to_group
from library.models import LibraryGroup, LibraryGroupMembership
from reading.models import Annotation, ReadingProgress, ReadingSession
from tests.utils.books import create_file_backed_book
from tests.utils.library_visibility import ensure_public_membership


User = get_user_model()


class SessionVisibilityFixtureMixin(IsolatedMediaRootMixin):
    def set_up_session_visibility_world(self):
        self.owner = User.objects.create_superuser(
            username="owner", password="pw", email="o@example.com"
        )
        ensure_public_membership(self.owner)

        self.user = User.objects.create_user(
            username="u", password="pw", email="u@example.com"
        )
        ensure_public_membership(self.user)
        self.client.login(username="u", password="pw")

        self.book = create_file_backed_book(title="Visible").book

        self.hidden_group = LibraryGroup.objects.create(name="Hidden")
        other = User.objects.create_user(
            username="other", password="pw", email="o@example.com"
        )
        ensure_public_membership(other)
        LibraryGroupMembership.objects.create(
            user=other, group=self.hidden_group, is_curator=False
        )

        self.hidden_book = create_file_backed_book(
            title="Hidden", assign_public=False
        ).book
        add_book_to_group(
            actor=self.owner, book=self.hidden_book, group=self.hidden_group
        )

        self.session_visible = ReadingSession.objects.create(
            user=self.user, book=self.book, name="S1"
        )
        ReadingProgress.objects.create(
            session=self.session_visible,
            current_location={"cfi": "/6/2"},
            progression=0.25,
        )
        Annotation.objects.create(
            session=self.session_visible,
            book=self.book,
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            selector_kind="epub_cfi",
            selector_value="epubcfi(/6/2)",
            highlight_text="hi",
        )
        Annotation.objects.create(
            session=self.session_visible,
            book=self.book,
            motivation=Annotation.MOTIVATION_COMMENTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            selector_kind="epub_cfi",
            selector_value="epubcfi(/6/4)",
            highlight_text="deleted",
            comment_text="deleted",
            is_deleted=True,
        )

        self.session_hidden = ReadingSession.objects.create(
            user=self.user, book=self.hidden_book, name="Secret"
        )


class SessionBearerFixtureMixin(IsolatedMediaRootMixin):
    def set_up_session_bearer_world(self):
        self.user = User.objects.create_user(
            username="u", password="pw", email="u@example.com"
        )
        ensure_public_membership(self.user)

        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
        self._auth = f"Bearer {token}"

        self.book = create_file_backed_book(title="Visible").book
        self.session = ReadingSession.objects.create(user=self.user, book=self.book)
